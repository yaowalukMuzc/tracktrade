//+------------------------------------------------------------------+
//|                                                  TrackTrade.mq5  |
//|  TrackTrade connector — pushes deals, open positions, SL/TP      |
//|  changes, symbol specs and price bars to the TrackTrade journal. |
//|  Wire contract: connectors/mt5-ea/PROTOCOL.md (v1).              |
//+------------------------------------------------------------------+
#property copyright   "TrackTrade"
#property link        "https://app.tracktrade.example"
#property version     "1.00"
#property description "TrackTrade journal connector: sends your trades to TrackTrade within seconds."
#property description "Does not place or change any orders."

#include <TrackTrade/Json.mqh>
#include <TrackTrade/Http.mqh>
#include <TrackTrade/Queue.mqh>
#include <TrackTrade/State.mqh>
#include <TrackTrade/Collect.mqh>

#define TT_EA_VERSION       "1.0.0"
#define TT_API_PATH         "/api/v1/ingest/events"
#define TT_MAX_ITEMS        500        // deals / modifications per request
#define TT_MAX_BARS         20000      // bars per request
#define TT_MAX_BODY_CHARS   1500000    // keep well below the 2 MB body limit
#define TT_HTTP_TIMEOUT_MS  8000
#define TT_OHLC_CHUNK_BARS  2000       // bars per queued ohlc item
#define TT_OHLC_MAX_BARS    100000     // per timeframe per command
#define TT_MAX_BACKOFF_SEC  60
#define TT_FLUSH_MAX_REQ    10         // requests per flush
#define TT_FLUSH_MAX_MS     3000       // time budget per flush

//--- inputs
input string ApiUrl         = "https://app.tracktrade.example"; // TrackTrade URL (add it in Tools › Options › Expert Advisors)
input string ApiKey         = "";                               // API key (tt_live_…) from Accounts › Connections
input int    HistoryDays    = 90;                               // Days of history imported on first run
input int    HeartbeatSec   = 10;                               // Heartbeat interval (seconds)
input int    OhlcBarsAround = 200;                              // Bars per timeframe when an ohlc command has no range

//--- pending OHLC work (CopyRates may need a few tries while history downloads)
struct TtOhlcJob
  {
   string            symbol;
   int               tf;          // ENUM_TIMEFRAMES
   long              from_utc;    // 0 = use OhlcBarsAround
   long              to_utc;
   int               tries;
  };

//--- configuration (inputs are read-only, so normalised copies live here)
string   g_endpoint       = "";
string   g_apiKey         = "";
int      g_historyDays    = 90;
int      g_heartbeatSec   = 10;
int      g_ohlcBarsAround = 200;
bool     g_inputsOk       = false;

//--- runtime
bool     g_ready          = false;   // login known, files loaded
long     g_login          = 0;
string   g_queueFile      = "";
string   g_stateFile      = "";
CTtQueue g_queue;
CTtState g_state;

bool     g_historyPending = false;
int      g_historyDaysReq = 0;
ulong    g_historyAtMs    = 0;

bool     g_authFailed     = false;
bool     g_urlBlocked     = false;
bool     g_alerted4014    = false;
int      g_failCount      = 0;
ulong    g_nextAttemptMs  = 0;
ulong    g_lastHeartbeatMs = 0;
int      g_batchLimit     = TT_MAX_ITEMS;

datetime g_lastSyncUtc    = 0;
uint     g_lastRttMs      = 0;
string   g_lastError      = "";
string   g_lastResult     = "";
string   g_unknownSymbols = "";
string   g_lastComment    = "";

string    g_sentSymbols[];            // symbol specs already accepted in this session
ulong     g_pendingDeals[];           // DEAL_ADD tickets not yet readable from history
int       g_pendingTries[];
TtOhlcJob g_ohlcJobs[];

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
ulong NowMs(void) { return GetTickCount64(); }

void SetError(const string msg)
  {
   g_lastError = TimeToString(TimeGMT(), TIME_SECONDS) + " UTC  " + msg;
   Print("TrackTrade: ", msg);
  }

void SaveState(void)
  {
   if(g_ready)
      g_state.Save(g_stateFile);
  }

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit(void)
  {
   if((bool)MQLInfoInteger(MQL_TESTER) || (bool)MQLInfoInteger(MQL_OPTIMIZATION))
     {
      Print("TrackTrade: WebRequest is not available in the Strategy Tester — attach the EA to a live chart.");
      return INIT_FAILED;
     }

   //--- validate inputs
   string url = ApiUrl;
   StringTrimLeft(url);
   StringTrimRight(url);
   while(StringLen(url) > 0 && StringGetCharacter(url, StringLen(url) - 1) == '/')
      url = StringSubstr(url, 0, StringLen(url) - 1);
   if(StringFind(url, "https://") != 0 && StringFind(url, "http://") != 0)
     {
      Alert("TrackTrade: ApiUrl ต้องขึ้นต้นด้วย https:// / ApiUrl must start with https:// (got \"", ApiUrl, "\")");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_endpoint = url + TT_API_PATH;

   g_apiKey = ApiKey;
   StringTrimLeft(g_apiKey);
   StringTrimRight(g_apiKey);
   if(g_apiKey == "")
     {
      Alert("TrackTrade: กรุณาใส่ ApiKey (คัดลอกจาก Accounts › การเชื่อมต่อ) / Please enter ApiKey (copy it from Accounts › Connections)");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(StringFind(g_apiKey, "tt_") != 0)
      Print("TrackTrade: warning — ApiKey does not look like a TrackTrade key (expected tt_live_…)");

   g_historyDays    = MathMax(1, MathMin(3650, HistoryDays));
   g_heartbeatSec   = MathMax(5, MathMin(300, HeartbeatSec));
   g_ohlcBarsAround = MathMax(10, MathMin(5000, OhlcBarsAround));
   g_inputsOk       = true;

   //--- reset per-session runtime (OnInit runs again when inputs or the account change)
   g_ready = false;
   g_authFailed = false;
   g_urlBlocked = false;
   g_alerted4014 = false;
   g_failCount = 0;
   g_nextAttemptMs = 0;
   g_lastHeartbeatMs = 0;
   g_batchLimit = TT_MAX_ITEMS;
   g_lastSyncUtc = 0;
   g_lastError = "";
   g_lastResult = "";
   g_unknownSymbols = "";
   g_lastComment = "";
   g_historyPending = false;
   ArrayResize(g_sentSymbols, 0);
   ArrayResize(g_pendingDeals, 0);
   ArrayResize(g_pendingTries, 0);
   ArrayResize(g_ohlcJobs, 0);

   if(!EventSetTimer(1))
     {
      Print("TrackTrade: EventSetTimer failed, error ", GetLastError());
      return INIT_FAILED;
     }

   TryStart();   // may be postponed to OnTimer until the terminal is connected
   UpdateStatus();
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_ready)
     {
      g_queue.Save();
      SaveState();
     }
   g_ready = false;
   Comment("");
  }

//+------------------------------------------------------------------+
//| Load files once the account login is known                       |
//+------------------------------------------------------------------+
bool TryStart(void)
  {
   if(g_ready)
      return true;
   if(!g_inputsOk)
      return false;
   long login = AccountInfoInteger(ACCOUNT_LOGIN);
   if(login <= 0 || !(bool)TerminalInfoInteger(TERMINAL_CONNECTED))
      return false;

   g_login     = login;
   string base = "TrackTrade\\" + IntegerToString(login);
   g_queueFile = base + ".queue";
   g_stateFile = base + ".state";
   FolderCreate("TrackTrade");

   g_queue.Load(g_queueFile);
   bool had_state = g_state.Load(g_stateFile);
   g_ready = true;

   if(!had_state || !g_state.history_done)
     {
      // First run: import history. Give the terminal a few seconds after
      // connecting to download the deal history before reading it.
      ScheduleHistory(g_historyDays, 3000);
      Print("TrackTrade: first run for account ", login, " — importing ", g_historyDays, " days of history");
     }
   else
      CatchUp();

   PollPositions();
   SaveState();
   PrintFormat("TrackTrade: started for account %I64d, %d item(s) queued, endpoint %s", login, g_queue.Count(), g_endpoint);
   return true;
  }

//+------------------------------------------------------------------+
//| Trade events -> send right away (latency target: < 5 s)          |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
      AddPendingDeal(trans.deal);
   else if(trans.type != TRADE_TRANSACTION_POSITION)
      return;   // SL/TP changes arrive as TRADE_TRANSACTION_POSITION; everything else is irrelevant

   if(!TryStart())
      return;   // the deal stays in g_pendingDeals until we can start
   ProcessPendingDeals();
   PollPositions();
   Flush(false);
   UpdateStatus();
  }

//+------------------------------------------------------------------+
//| 1-second timer: retries, heartbeat, polling, commands            |
//+------------------------------------------------------------------+
void OnTimer(void)
  {
   if(!TryStart())
     {
      UpdateStatus();
      return;
     }

   if(g_historyPending && NowMs() >= g_historyAtMs)
     {
      if(EnqueueHistory(g_historyDaysReq))
        {
         g_historyPending = false;
         g_state.history_done = true;
         SaveState();
        }
      else
         g_historyAtMs = NowMs() + 5000;   // history not available yet — retry
     }

   ProcessPendingDeals();
   PollPositions();
   ProcessOhlcJobs();

   bool heartbeat_due = (NowMs() - g_lastHeartbeatMs >= (ulong)g_heartbeatSec * 1000);
   Flush(heartbeat_due);
   UpdateStatus();
  }

//+------------------------------------------------------------------+
//| Deals                                                            |
//+------------------------------------------------------------------+
void AddPendingDeal(const ulong ticket)
  {
   if(ticket == 0)
      return;
   int n = ArraySize(g_pendingDeals);
   for(int i = 0; i < n; i++)
      if(g_pendingDeals[i] == ticket)
         return;
   ArrayResize(g_pendingDeals, n + 1);
   ArrayResize(g_pendingTries, n + 1);
   g_pendingDeals[n] = ticket;
   g_pendingTries[n] = 0;
  }

// Queue line for one deal (the deal must be selected / in the history cache).
string DealLine(const ulong ticket)
  {
   string sym;
   long utc;
   string json = TtDealJson(ticket, sym, utc);
   return "D\t" + sym + "\t" + IntegerToString(utc) + "\t" + json;
  }

void NoteDealTime(const ulong ticket)
  {
   long msc = TtDealTimeMsc(ticket);
   if(msc > g_state.last_deal_msc)
      g_state.last_deal_msc = msc;
  }

// Queue deals reported by OnTradeTransaction once HistoryDealSelect can see them.
void ProcessPendingDeals(void)
  {
   if(!g_ready)
      return;
   int n = ArraySize(g_pendingDeals);
   if(n == 0)
      return;
   string lines[];
   int nl = 0;
   int keep = 0;
   for(int i = 0; i < n; i++)
     {
      ulong t = g_pendingDeals[i];
      if(HistoryDealSelect(t))
        {
         if(TtDealIsTrade(t))   // skip balance / credit / commission-only deals
           {
            ArrayResize(lines, nl + 1);
            lines[nl++] = DealLine(t);
            NoteDealTime(t);
           }
         continue;
        }
      if(++g_pendingTries[i] >= 30)
        {
         SetError("deal " + IntegerToString((long)t) + " not found in history, skipped (will be sent by the next resync)");
         continue;
        }
      g_pendingDeals[keep] = t;
      g_pendingTries[keep] = g_pendingTries[i];
      keep++;
     }
   ArrayResize(g_pendingDeals, keep);
   ArrayResize(g_pendingTries, keep);
   if(nl > 0)
     {
      g_queue.Push(lines, nl);
      SaveState();
     }
  }

// After a restart: resend every deal since the state was last saved (minus 1 h),
// i.e. everything that happened while the EA/terminal was off.
// The server de-duplicates by ticket, so overlap is harmless.
void CatchUp(void)
  {
   long now_srv  = (long)TimeTradeServer();
   long from_srv = (g_state.saved_srv > 0) ? g_state.saved_srv : now_srv - 86400;
   from_srv -= 3600;
   if(!HistorySelect((datetime)from_srv, (datetime)(now_srv + 86400)))
      return;
   int total = HistoryDealsTotal();
   string lines[];
   int nl = 0;
   for(int i = 0; i < total; i++)
     {
      ulong t = HistoryDealGetTicket(i);
      if(t == 0 || !TtDealIsTrade(t))
         continue;
      ArrayResize(lines, nl + 1, total);
      lines[nl++] = DealLine(t);
      NoteDealTime(t);
     }
   if(nl > 0)
     {
      g_queue.Push(lines, nl);
      PrintFormat("TrackTrade: catch-up queued %d deal(s) since the last run", nl);
     }
  }

void ScheduleHistory(const int days, const int delay_ms)
  {
   int d = MathMax(1, MathMin(3650, days));
   if(g_historyPending)
      g_historyDaysReq = MathMax(g_historyDaysReq, d);
   else
      g_historyDaysReq = d;
   g_historyPending = true;
   g_historyAtMs    = NowMs() + (ulong)delay_ms;
  }

// Queue all deals of the last `days` days as history chunks:
// oldest first, <= 500 deals per chunk, final=1 on the last one.
bool EnqueueHistory(const int days)
  {
   long now_srv  = (long)TimeTradeServer();
   long from_srv = now_srv - (long)days * 86400;
   if(!HistorySelect((datetime)from_srv, (datetime)(now_srv + 86400)))
     {
      SetError("HistorySelect failed, error " + IntegerToString(GetLastError()));
      return false;
     }
   int total = HistoryDealsTotal();

   //--- collect [time_msc, ticket] of trade deals and sort by time
   long keys[][2];
   ArrayResize(keys, total);
   int n = 0;
   for(int i = 0; i < total; i++)
     {
      ulong t = HistoryDealGetTicket(i);
      if(t == 0 || !TtDealIsTrade(t))
         continue;
      keys[n][0] = TtDealTimeMsc(t);
      keys[n][1] = (long)t;
      n++;
     }
   ArrayResize(keys, n);
   if(n > 1)
      ArraySort(keys);   // sorts rows by the first column (time_msc)

   long from_utc = TtServerToUtc(from_srv);
   long to_utc   = (long)TimeGMT();

   string lines[];
   ArrayResize(lines, 0, n + n / TT_MAX_ITEMS + 2);
   int nl = 0;
   if(n == 0)
     {
      //--- nothing to import: still tell the server the import is complete
      ArrayResize(lines, 1);
      lines[0] = "H\t" + IntegerToString(from_utc) + "\t" + IntegerToString(to_utc) + "\t1\t0";
      nl = 1;
     }
   for(int start = 0; start < n; start += TT_MAX_ITEMS)
     {
      int cnt = MathMin(TT_MAX_ITEMS, n - start);
      bool last = (start + cnt >= n);
      string chunk_lines[];
      ArrayResize(chunk_lines, cnt);
      long first_utc = 0, last_utc = 0;
      for(int k = 0; k < cnt; k++)
        {
         ulong t = (ulong)keys[start + k][1];
         string sym;
         long utc;
         string json = TtDealJson(t, sym, utc);
         chunk_lines[k] = "D\t" + sym + "\t" + IntegerToString(utc) + "\t" + json;
         if(k == 0)
            first_utc = utc;
         last_utc = utc;
         NoteDealTime(t);
        }
      long c_from = (start == 0) ? from_utc : first_utc;
      long c_to   = last ? to_utc : last_utc;
      ArrayResize(lines, nl + 1 + cnt, n + n / TT_MAX_ITEMS + 2);
      lines[nl++] = "H\t" + IntegerToString(c_from) + "\t" + IntegerToString(c_to) + "\t"
                    + (last ? "1" : "0") + "\t" + IntegerToString(cnt);
      for(int k = 0; k < cnt; k++)
         lines[nl++] = chunk_lines[k];
     }
   g_queue.Push(lines, nl);
   PrintFormat("TrackTrade: history import queued — %d deal(s) over %d day(s)", n, days);
   g_lastResult = "history import: " + IntegerToString(n) + " deal(s) queued";
   return true;
  }

//+------------------------------------------------------------------+
//| SL/TP modifications: compare open positions with the last known  |
//| SL/TP (runs every second and on TRADE_TRANSACTION_POSITION)       |
//+------------------------------------------------------------------+
string ModLine(const long pid, const string sym, const string field,
               const double old_v, const double new_v, long update_msc)
  {
   if(update_msc <= 0)
      update_msc = (long)TimeTradeServer() * 1000;
   return "M\t" + sym + "\t" + IntegerToString(TtServerToUtc(update_msc / 1000)) + "\t"
          + TtModJson(pid, sym, field, old_v, new_v, update_msc);
  }

void PollPositions(void)
  {
   if(!g_ready)
      return;
   TtPos p[];
   int n = TtReadPositions(p);
   string lines[];
   int nl = 0;
   bool changed = false;

   for(int i = 0; i < n; i++)
     {
      double point = TtSymbolPoint(p[i].symbol);
      int k = g_state.Find(p[i].id);
      double old_sl, old_tp;
      if(k < 0)
        {
         //--- first time we see this position: baseline = SL/TP of the opening deal,
         //    so a change made before we noticed the position is still reported.
         old_sl = p[i].sl;
         old_tp = p[i].tp;
         if(p[i].update_msc > p[i].time_msc)
           {
            double dsl = 0.0, dtp = 0.0;
            if(TtOpeningSlTp(p[i].id, dsl, dtp))
              {
               old_sl = dsl;
               old_tp = dtp;
              }
           }
        }
      else
        {
         old_sl = g_state.pos[k].sl;
         old_tp = g_state.pos[k].tp;
        }

      if(!TtSamePrice(old_sl, p[i].sl, point))
        {
         ArrayResize(lines, nl + 1);
         lines[nl++] = ModLine(p[i].id, p[i].symbol, "sl", old_sl, p[i].sl, p[i].update_msc);
        }
      if(!TtSamePrice(old_tp, p[i].tp, point))
        {
         ArrayResize(lines, nl + 1);
         lines[nl++] = ModLine(p[i].id, p[i].symbol, "tp", old_tp, p[i].tp, p[i].update_msc);
        }
      //--- remember the new SL/TP (short-circuit: pos[k] is only read when k >= 0)
      if(k < 0 || !TtSamePrice(g_state.pos[k].sl, p[i].sl, point) || !TtSamePrice(g_state.pos[k].tp, p[i].tp, point))
        {
         g_state.Upsert(p[i].id, p[i].sl, p[i].tp, p[i].update_msc);
         changed = true;
        }
     }

   //--- forget closed positions
   for(int k = ArraySize(g_state.pos) - 1; k >= 0; k--)
     {
      bool open = false;
      for(int i = 0; i < n; i++)
         if(p[i].id == g_state.pos[k].id)
           {
            open = true;
            break;
           }
      if(!open)
        {
         g_state.RemoveAt(k);
         changed = true;
        }
     }

   if(nl > 0)
      g_queue.Push(lines, nl);
   if(changed || nl > 0)
      SaveState();
  }

//+------------------------------------------------------------------+
//| OHLC command jobs                                                |
//+------------------------------------------------------------------+
void AddOhlcJob(const string sym, const ENUM_TIMEFRAMES tf, const long from_utc, const long to_utc)
  {
   int n = ArraySize(g_ohlcJobs);
   ArrayResize(g_ohlcJobs, n + 1);
   g_ohlcJobs[n].symbol   = sym;
   g_ohlcJobs[n].tf       = (int)tf;
   g_ohlcJobs[n].from_utc = from_utc;
   g_ohlcJobs[n].to_utc   = to_utc;
   g_ohlcJobs[n].tries    = 0;
  }

// Returns true when the job is finished (sent or given up).
bool RunOhlcJob(TtOhlcJob &job)
  {
   ENUM_TIMEFRAMES tf = (ENUM_TIMEFRAMES)job.tf;
   string tf_name = TtTfName(tf);
   if(!(bool)SymbolInfoInteger(job.symbol, SYMBOL_SELECT))
      SymbolSelect(job.symbol, true);   // CopyRates needs the symbol in Market Watch

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   ResetLastError();
   int got;
   if(job.from_utc > 0 && job.to_utc > 0)
     {
      long from_srv = TtUtcToServer(job.from_utc);
      long to_srv   = TtUtcToServer(MathMin(job.to_utc, (long)TimeGMT()));
      long max_span = (long)PeriodSeconds(tf) * TT_OHLC_MAX_BARS;
      if(to_srv - from_srv > max_span)
         from_srv = to_srv - max_span;
      got = CopyRates(job.symbol, tf, (datetime)from_srv, (datetime)to_srv, rates);
     }
   else
      got = CopyRates(job.symbol, tf, 0, g_ohlcBarsAround, rates);

   if(got <= 0)
     {
      int err = GetLastError();
      if(++job.tries >= 10)
        {
         SetError("ohlc " + job.symbol + " " + tf_name + ": no bars (error " + IntegerToString(err) + ")");
         return true;
        }
      return false;   // history may still be downloading — retry next second
     }

   string lines[];
   int nl = 0;
   for(int start = 0; start < got; start += TT_OHLC_CHUNK_BARS)
     {
      int cnt = MathMin(TT_OHLC_CHUNK_BARS, got - start);
      ArrayResize(lines, nl + 1);
      lines[nl++] = "O\t" + job.symbol + "\t" + IntegerToString(cnt) + "\t"
                    + TtOhlcJson(job.symbol, tf_name, rates, start, cnt);
     }
   g_queue.Push(lines, nl);
   return true;
  }

void ProcessOhlcJobs(void)
  {
   int n = ArraySize(g_ohlcJobs);
   if(n == 0)
      return;
   int keep = 0;
   int budget = 4;   // CopyRates calls per tick
   for(int i = 0; i < n; i++)
     {
      bool done = false;
      if(budget > 0)
        {
         budget--;
         done = RunOhlcJob(g_ohlcJobs[i]);
        }
      if(!done)
        {
         if(keep != i)
            g_ohlcJobs[keep] = g_ohlcJobs[i];
         keep++;
        }
     }
   ArrayResize(g_ohlcJobs, keep);
  }

//+------------------------------------------------------------------+
//| Request building                                                 |
//+------------------------------------------------------------------+
// Builds the next request from the head of the queue. `consumed` is the
// number of queue lines it covers; `syms` the symbols whose spec is
// included (marked as sent after a 2xx).
string BuildBatch(int &consumed, string &syms[])
  {
   string deals = "", mods = "", ohlc = "", history = "";
   int nd = 0, nm = 0, no = 0, bars = 0, chars = 0;
   string used[];   // symbols appearing in this request
   consumed = 0;
   int count = g_queue.Count();
   string f[];

   if(count > 0 && StringGetCharacter(g_queue.At(0), 0) == 'H')
     {
      //--- a history chunk is always sent alone, with its "history" window
      string h[];
      StringSplit(g_queue.At(0), (ushort)9, h);
      int cnt = (ArraySize(h) >= 5) ? (int)StringToInteger(h[4]) : 0;
      if(ArraySize(h) >= 5)
         history = "{\"from\":" + h[1] + ",\"to\":" + h[2] + ",\"final\":" + (h[3] == "1" ? "true" : "false") + "}";
      consumed = 1;
      for(int k = 0; k < cnt && consumed < count; k++)
        {
         string line = g_queue.At(consumed);
         if(StringGetCharacter(line, 0) != 'D' || StringSplit(line, (ushort)9, f) < 4)
            break;
         if(nd > 0)
            deals += ",";
         deals += f[3];
         nd++;
         TtAddUnique(used, f[1]);
         consumed++;
        }
     }
   else
     {
      //--- live items: deals, modifications, ohlc
      while(consumed < count && consumed < g_batchLimit)
        {
         string line = g_queue.At(consumed);
         ushort kind = StringGetCharacter(line, 0);
         if(kind == 'H')
            break;
         if(StringSplit(line, (ushort)9, f) < 4)
           {
            consumed++;   // malformed line: drop it with the batch
            continue;
           }
         int len = StringLen(f[3]);
         if(consumed > 0 && chars + len > TT_MAX_BODY_CHARS)
            break;
         if(kind == 'O')
           {
            int nb = (int)StringToInteger(f[2]);
            if(consumed > 0 && bars + nb > TT_MAX_BARS)
               break;
            bars += nb;
            if(no > 0)
               ohlc += ",";
            ohlc += f[3];
            no++;
           }
         else if(kind == 'D')
           {
            if(nd > 0)
               deals += ",";
            deals += f[3];
            nd++;
           }
         else if(kind == 'M')
           {
            if(nm > 0)
               mods += ",";
            mods += f[3];
            nm++;
           }
         chars += len;
         TtAddUnique(used, f[1]);
         consumed++;
        }
     }

   //--- open positions snapshot (every request doubles as a heartbeat)
   TtPos p[];
   int np = TtReadPositions(p);
   string positions = "";
   for(int i = 0; i < np; i++)
     {
      if(i > 0)
         positions += ",";
      positions += TtPositionJson(p[i]);
      TtAddUnique(used, p[i].symbol);
     }

   //--- symbol specs not yet accepted in this session
   string symbols = "";
   ArrayResize(syms, 0);
   for(int i = 0; i < ArraySize(used); i++)
     {
      if(TtContains(g_sentSymbols, used[i]))
         continue;
      if(ArraySize(syms) > 0)
         symbols += ",";
      symbols += TtSymbolJson(used[i]);
      TtAddUnique(syms, used[i]);
     }

   string body = "{\"ea_version\":" + TtQ(TT_EA_VERSION);
   body += ",\"sent_at\":" + IntegerToString((long)TimeGMT());
   body += ",\"account\":" + TtAccountJson();
   body += ",\"symbols\":[" + symbols + "]";
   body += ",\"deals\":[" + deals + "]";
   body += ",\"positions\":[" + positions + "]";
   body += ",\"modifications\":[" + mods + "]";
   body += ",\"ohlc\":[" + ohlc + "]";
   if(history != "")
      body += ",\"history\":" + history;
   body += "}";
   return body;
  }

//+------------------------------------------------------------------+
//| Sending                                                          |
//+------------------------------------------------------------------+
void Backoff(const int retry_after_sec)
  {
   g_failCount++;
   int delay = (int)MathMin(TT_MAX_BACKOFF_SEC, MathPow(2.0, MathMin(g_failCount - 1, 6)));   // 1,2,4…60
   if(retry_after_sec > 0)
      delay = retry_after_sec;
   g_nextAttemptMs = NowMs() + (ulong)delay * 1000;
  }

// 413 on a history chunk: split it into two chunks (first one never final).
bool SplitHistoryHead(void)
  {
   string h[];
   if(StringSplit(g_queue.At(0), (ushort)9, h) < 5)
      return false;
   int cnt = (int)StringToInteger(h[4]);
   if(cnt < 2 || g_queue.Count() < 1 + cnt)
      return false;
   int n1 = cnt / 2;
   int n2 = cnt - n1;
   string f[];
   string mid1 = h[2], mid2 = h[1];
   if(StringSplit(g_queue.At(n1), (ushort)9, f) >= 4)
      mid1 = f[2];                     // time of the last deal of the first half
   if(StringSplit(g_queue.At(n1 + 1), (ushort)9, f) >= 4)
      mid2 = f[2];                     // time of the first deal of the second half
   g_queue.Set(0, "H\t" + h[1] + "\t" + mid1 + "\t0\t" + IntegerToString(n1));
   g_queue.Insert(1 + n1, "H\t" + mid2 + "\t" + h[2] + "\t" + h[3] + "\t" + IntegerToString(n2));
   g_queue.Save();
   return true;
  }

// Send one request. Returns 1 = sent, 0 = retry immediately (batch was
// re-split), -1 = failed (backoff scheduled), -2 = stopped (401).
int SendOnce(void)
  {
   int consumed = 0;
   string syms[];
   string body = BuildBatch(consumed, syms);

   TtHttpResult res;
   TtHttpPostJson(g_endpoint, g_apiKey, body, TT_HTTP_TIMEOUT_MS, "TrackTrade-MT5-EA/" + TT_EA_VERSION, res);
   g_lastRttMs = res.rtt_ms;

   //--- transport failure
   if(res.status == -1)
     {
      if(res.error == TT_ERR_WEBREQUEST_NOT_ALLOWED)
        {
         g_urlBlocked = true;
         SetError("WebRequest not allowed for this URL (error 4014)");
         if(!g_alerted4014)
           {
            g_alerted4014 = true;
            string base = StringSubstr(g_endpoint, 0, StringLen(g_endpoint) - StringLen(TT_API_PATH));
            Alert("TrackTrade: MT5 ยังไม่อนุญาตให้ EA เชื่อมต่อ ", base,
                  "\nไปที่ Tools › Options › Expert Advisors › ติ๊ก \"Allow WebRequest for listed URL\" แล้วเพิ่ม ", base,
                  "\nMT5 blocks the connection: open Tools › Options › Expert Advisors, tick \"Allow WebRequest for listed URL\" and add ", base);
           }
        }
      else
         SetError("network error " + IntegerToString(res.error) + " (no response from server)");
      Backoff(0);
      return -1;
     }
   g_urlBlocked = false;

   //--- success
   if(res.status >= 200 && res.status < 300)
     {
      g_queue.RemoveHead(consumed);
      for(int i = 0; i < ArraySize(syms); i++)
         TtAddUnique(g_sentSymbols, syms[i]);
      g_failCount       = 0;
      g_nextAttemptMs   = 0;
      g_batchLimit      = MathMin(TT_MAX_ITEMS, g_batchLimit * 2);
      g_lastSyncUtc     = TimeGMT();
      g_lastHeartbeatMs = NowMs();
      HandleResponse(res.body);
      return 1;
     }

   //--- invalid key: stop until the user changes the input (that re-runs OnInit)
   if(res.status == 401)
     {
      g_authFailed = true;
      SetError("401 invalid API key — sending stopped");
      return -2;
     }

   //--- too large: split
   if(res.status == 413)
     {
      SetError("413 payload too large — splitting the batch");
      if(consumed > 0 && StringGetCharacter(g_queue.At(0), 0) == 'H')
        {
         if(SplitHistoryHead())
            return 0;
        }
      else if(consumed > 1)
        {
         g_batchLimit = MathMax(1, consumed / 2);
         return 0;
        }
      Print("TrackTrade: a single item is too large and was dropped: ", StringSubstr(body, 0, 500));
      g_queue.RemoveHead(consumed);
      g_lastHeartbeatMs = NowMs();
      return 0;
     }

   //--- validation error: will never succeed -> log and drop
   if(res.status == 422)
     {
      SetError("422 validation error — batch dropped (see Experts log)");
      Print("TrackTrade: 422 response: ", res.body);
      Print("TrackTrade: rejected body (first 2000 chars): ", StringSubstr(body, 0, 2000));
      g_queue.RemoveHead(consumed);
      g_lastHeartbeatMs = NowMs();
      g_failCount = 0;
      return 1;
     }

   //--- rate limited
   if(res.status == 429)
     {
      SetError("429 rate limited — waiting " + IntegerToString(res.retry_after) + " s");
      Backoff(res.retry_after);
      return -1;
     }

   //--- 5xx and anything else: keep the batch, retry with backoff
   SetError("HTTP " + IntegerToString(res.status) + " " + StringSubstr(res.body, 0, 200));
   Backoff(0);
   return -1;
  }

// Send queued items (and/or a heartbeat) within a small time budget.
void Flush(bool heartbeat)
  {
   if(!g_ready || g_authFailed)
      return;
   if(NowMs() < g_nextAttemptMs)
      return;
   ulong started = NowMs();
   int requests = 0;
   while(g_queue.Count() > 0 || heartbeat)
     {
      int r = SendOnce();
      if(r < 0)
         break;
      heartbeat = false;   // every request carries account + positions
      requests++;
      if(requests >= TT_FLUSH_MAX_REQ || NowMs() - started > TT_FLUSH_MAX_MS)
         break;
     }
  }

//+------------------------------------------------------------------+
//| Response: counters, unknown symbols, commands                    |
//+------------------------------------------------------------------+
void HandleResponse(const string body)
  {
   if(body == "")
      return;
   CTtJsonParser parser;
   CTtJson *root = parser.Parse(body);
   if(root == NULL)
     {
      SetError("could not parse the server response");
      return;
     }

   CTtJson *acc = root.Get("accepted");
   CTtJson *dup = root.Get("duplicates");
   if(acc != NULL)
     {
      g_lastResult = StringFormat("accepted %I64d deal(s), %I64d mod(s), %I64d bar(s)",
                                  acc.Long("deals"), acc.Long("modifications"), acc.Long("bars"));
      if(dup != NULL)
         g_lastResult += StringFormat("; duplicates %I64d/%I64d/%I64d",
                                      dup.Long("deals"), dup.Long("modifications"), dup.Long("bars"));
     }

   CTtJson *unk = root.Get("unknown_symbols");
   if(unk != NULL && unk.m_type == TTJ_ARRAY)
     {
      string s = "";
      for(int i = 0; i < unk.Size(); i++)
        {
         CTtJson *u = unk.At(i);
         if(u == NULL)
            continue;
         if(s != "")
            s += ", ";
         s += u.m_value;
        }
      g_unknownSymbols = s;
     }

   CTtJson *cmds = root.Get("commands");
   if(cmds != NULL && cmds.m_type == TTJ_ARRAY)
      for(int i = 0; i < cmds.Size(); i++)
         ExecuteCommand(cmds.At(i));

   delete root;
  }

void ExecuteCommand(CTtJson *cmd)
  {
   if(cmd == NULL || cmd.m_type != TTJ_OBJECT)
      return;
   string id   = cmd.Str("id");
   string kind = cmd.Str("kind");
   CTtJson *params = cmd.Get("params");
   PrintFormat("TrackTrade: command %s (%s)", kind, id);

   if(kind == "resync")
     {
      int days = g_historyDays;
      if(params != NULL)
         days = (int)params.Long("days", g_historyDays);
      ScheduleHistory(days, 0);
      return;
     }

   if(kind == "ohlc")
     {
      if(params == NULL)
         return;
      string sym = params.Str("symbol");
      if(sym == "")
         return;
      long from_utc = params.Long("from", 0);
      long to_utc   = params.Long("to", 0);
      long around   = params.Long("time", 0);   // optional: centre time when no range is given

      string tfs[];
      CTtJson *arr = params.Get("timeframes");
      if(arr != NULL && arr.m_type == TTJ_ARRAY)
        {
         for(int i = 0; i < arr.Size(); i++)
            if(arr.At(i) != NULL)
               TtAddUnique(tfs, arr.At(i).m_value);
        }
      if(ArraySize(tfs) == 0)
        {
         string all[] = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"};
         for(int i = 0; i < ArraySize(all); i++)
            TtAddUnique(tfs, all[i]);
        }

      for(int i = 0; i < ArraySize(tfs); i++)
        {
         ENUM_TIMEFRAMES tf = PERIOD_M1;
         if(!TtTfFromName(tfs[i], tf))
           {
            Print("TrackTrade: unsupported timeframe ", tfs[i]);
            continue;
           }
         long f = from_utc, t = to_utc;
         if((f <= 0 || t <= 0) && around > 0)
           {
            long span = (long)PeriodSeconds(tf) * g_ohlcBarsAround;
            f = around - span;
            t = around + span;
           }
         AddOhlcJob(sym, tf, f, t);
        }
      return;
     }

   Print("TrackTrade: unknown command kind '", kind, "' ignored");
  }

//+------------------------------------------------------------------+
//| Chart status                                                     |
//+------------------------------------------------------------------+
void UpdateStatus(void)
  {
   string s = "TrackTrade EA " + TT_EA_VERSION;
   if(g_login > 0)
      s += "   #" + IntegerToString(g_login) + "  " + AccountInfoString(ACCOUNT_SERVER);
   s += "\n";

   if(g_authFailed)
      s += "!! API key ไม่ถูกต้อง / invalid API key — หยุดส่งข้อมูลแล้ว / sending stopped\n"
           + "   กด F7 แล้วแก้ ApiKey (คัดลอกจาก Accounts › การเชื่อมต่อ)\n"
           + "   Press F7 and fix ApiKey (copy it from Accounts › Connections)\n";
   else if(g_urlBlocked)
      s += "!! MT5 บล็อก WebRequest / WebRequest blocked\n"
           + "   Tools › Options › Expert Advisors › Allow WebRequest for listed URL → เพิ่ม/add URL ของ TrackTrade\n";
   else if(!g_ready)
      s += "สถานะ / Status: รอเทอร์มินัลเชื่อมต่อโบรกเกอร์ / waiting for the terminal to connect\n";
   else if(g_failCount > 0)
     {
      long wait = (g_nextAttemptMs > NowMs()) ? (long)((g_nextAttemptMs - NowMs()) / 1000) + 1 : 0;
      s += "สถานะ / Status: ออฟไลน์ ลองใหม่ใน " + IntegerToString(wait) + " วิ / offline, retry in " + IntegerToString(wait) + " s\n";
     }
   else if(g_lastSyncUtc > 0)
      s += "สถานะ / Status: เชื่อมต่อแล้ว / connected\n";
   else
      s += "สถานะ / Status: กำลังเชื่อมต่อ… / connecting…\n";

   s += "ซิงก์ล่าสุด / Last sync: ";
   if(g_lastSyncUtc > 0)
      s += TimeToString(g_lastSyncUtc, TIME_DATE | TIME_SECONDS) + " UTC (" + IntegerToString(g_lastRttMs) + " ms)";
   else
      s += "-";
   s += "\n";

   s += "รอส่ง / Queued: " + IntegerToString(g_queue.Count()) + " item(s)";
   if(g_historyPending)
      s += " + ประวัติย้อนหลัง / history import pending";
   s += "\n";
   if(g_lastResult != "")
      s += "ผลล่าสุด / Last result: " + g_lastResult + "\n";
   if(g_unknownSymbols != "")
      s += "สัญลักษณ์ที่ยังไม่แมป / Unmapped symbols: " + g_unknownSymbols + "\n";
   s += "ข้อผิดพลาดล่าสุด / Last error: " + (g_lastError == "" ? "-" : g_lastError);

   if(s != g_lastComment)
     {
      g_lastComment = s;
      Comment(s);
     }
  }
//+------------------------------------------------------------------+
