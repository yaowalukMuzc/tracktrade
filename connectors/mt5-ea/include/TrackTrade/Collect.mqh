//+------------------------------------------------------------------+
//| TrackTrade/Collect.mqh                                           |
//| MT5 objects -> protocol JSON fragments (account, symbol spec,    |
//| deal, position, modification, ohlc) + time/number formatting.    |
//| See connectors/mt5-ea/PROTOCOL.md.                               |
//+------------------------------------------------------------------+
#ifndef TT_COLLECT_MQH
#define TT_COLLECT_MQH

#include "Json.mqh"

//+------------------------------------------------------------------+
//| Time                                                             |
//+------------------------------------------------------------------+
// Broker server time minus UTC, in seconds. TimeTradeServer() and
// TimeGMT() are both derived from the local PC clock but sampled at
// slightly different moments, so the raw difference can be off by a
// second; real time zones are multiples of 15 minutes -> round to 900 s.
long TtServerOffsetSec(void)
  {
   long diff = (long)TimeTradeServer() - (long)TimeGMT();
   long q = 900;
   if(diff >= 0)
      return ((diff + q / 2) / q) * q;
   return -(((-diff) + q / 2) / q) * q;
  }

long TtServerToUtc(const long server_sec) { return server_sec - TtServerOffsetSec(); }
long TtUtcToServer(const long utc_sec)    { return utc_sec + TtServerOffsetSec(); }

//+------------------------------------------------------------------+
//| Numbers (always sent as JSON strings)                            |
//+------------------------------------------------------------------+
string TtFixed(double v, int digits)
  {
   if(digits < 0)
      digits = 0;
   if(digits > 8)
      digits = 8;
   if(MathAbs(v) < 0.5 * MathPow(10.0, -digits))
      v = 0.0;                       // avoid "-0.00"
   return DoubleToString(v, digits);
  }

// Fixed with up to maxd decimals, trailing zeros removed ("100", "0.01").
string TtTrim(const double v, const int maxd)
  {
   string s = TtFixed(v, maxd);
   if(StringFind(s, ".") < 0)
      return s;
   int n = StringLen(s);
   while(n > 0 && StringGetCharacter(s, n - 1) == '0')
      n--;
   if(n > 0 && StringGetCharacter(s, n - 1) == '.')
      n--;
   return StringSubstr(s, 0, n);
  }

int TtSymbolDigits(const string sym)
  {
   long d = 0;
   if(SymbolInfoInteger(sym, SYMBOL_DIGITS, d))
      return (int)d;
   return 5;   // unknown symbol: be generous
  }

double TtSymbolPoint(const string sym)
  {
   double p = 0.0;
   if(SymbolInfoDouble(sym, SYMBOL_POINT, p) && p > 0.0)
      return p;
   return 0.00001;
  }

// 2 decimals per protocol, more if the broker allows smaller steps (e.g. 0.001 lots).
int TtVolumeDigits(const string sym)
  {
   double step = 0.0;
   SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP, step);
   int d = 2;
   while(d < 8 && step > 0.0)
     {
      double scaled = step * MathPow(10.0, d);
      if(MathAbs(scaled - MathRound(scaled)) < 1e-6)
         break;
      d++;
     }
   return d;
  }

string TtPrice(const double v, const int digits) { return TtFixed(v, digits); }
// SL/TP: "0" means not set.
string TtPriceOrZero(const double v, const int digits) { return (v == 0.0) ? "0" : TtFixed(v, digits); }
string TtMoney(const double v) { return TtFixed(v, 2); }
string TtVolume(const double v, const string sym) { return TtFixed(v, TtVolumeDigits(sym)); }

// Same price within half a point.
bool TtSamePrice(const double a, const double b, const double point)
  {
   return MathAbs(a - b) < point * 0.5;
  }

// Add s to arr if not present.
void TtAddUnique(string &arr[], const string s)
  {
   if(s == "")
      return;
   int n = ArraySize(arr);
   for(int i = 0; i < n; i++)
      if(arr[i] == s)
         return;
   ArrayResize(arr, n + 1);
   arr[n] = s;
  }

bool TtContains(const string &arr[], const string s)
  {
   int n = ArraySize(arr);
   for(int i = 0; i < n; i++)
      if(arr[i] == s)
         return true;
   return false;
  }

//+------------------------------------------------------------------+
//| Account                                                          |
//+------------------------------------------------------------------+
string TtAccountJson(void)
  {
   ENUM_ACCOUNT_MARGIN_MODE mm = (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   string mode = (mm == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) ? "hedging" : "netting";
   string j = "{";
   j += "\"login\":"        + TtQ(IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)));
   j += ",\"server\":"      + TtQ(AccountInfoString(ACCOUNT_SERVER));
   j += ",\"company\":"     + TtQ(AccountInfoString(ACCOUNT_COMPANY));
   j += ",\"currency\":"    + TtQ(AccountInfoString(ACCOUNT_CURRENCY));
   j += ",\"balance\":"     + TtQ(TtMoney(AccountInfoDouble(ACCOUNT_BALANCE)));
   j += ",\"equity\":"      + TtQ(TtMoney(AccountInfoDouble(ACCOUNT_EQUITY)));
   j += ",\"margin_mode\":" + TtQ(mode);
   j += "}";
   return j;
  }

//+------------------------------------------------------------------+
//| Symbol spec                                                      |
//+------------------------------------------------------------------+
string TtSymbolJson(const string sym)
  {
   // tick_value of a symbol that is not in Market Watch can be 0 (no quotes yet)
   if(!(bool)SymbolInfoInteger(sym, SYMBOL_SELECT))
      SymbolSelect(sym, true);
   int digits = TtSymbolDigits(sym);
   string j = "{";
   j += "\"name\":"             + TtQ(sym);
   j += ",\"digits\":"          + IntegerToString(digits);
   j += ",\"point\":"           + TtQ(TtFixed(SymbolInfoDouble(sym, SYMBOL_POINT), digits));
   j += ",\"contract_size\":"   + TtQ(TtTrim(SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE), 8));
   j += ",\"tick_size\":"       + TtQ(TtFixed(SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE), digits));
   j += ",\"tick_value\":"      + TtQ(TtTrim(SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE), 8));
   j += ",\"volume_step\":"     + TtQ(TtTrim(SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP), 8));
   j += ",\"volume_min\":"      + TtQ(TtTrim(SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN), 8));
   j += ",\"volume_max\":"      + TtQ(TtTrim(SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX), 8));
   j += ",\"currency_base\":"   + TtQ(SymbolInfoString(sym, SYMBOL_CURRENCY_BASE));
   j += ",\"currency_profit\":" + TtQ(SymbolInfoString(sym, SYMBOL_CURRENCY_PROFIT));
   j += "}";
   return j;
  }

//+------------------------------------------------------------------+
//| Deals (the deal must be reachable in history: after HistorySelect |
//| or HistoryDealSelect)                                            |
//+------------------------------------------------------------------+
bool TtDealIsTrade(const ulong ticket)
  {
   long type = HistoryDealGetInteger(ticket, DEAL_TYPE);
   return (type == DEAL_TYPE_BUY || type == DEAL_TYPE_SELL);
  }

string TtDealEntryName(const long entry)
  {
   if(entry == DEAL_ENTRY_IN)
      return "in";
   if(entry == DEAL_ENTRY_OUT)
      return "out";
   if(entry == DEAL_ENTRY_INOUT)
      return "inout";
   if(entry == DEAL_ENTRY_OUT_BY)
      return "out_by";
   return "in";
  }

// Server-time msc of a deal (DEAL_TIME_MSC, fallback DEAL_TIME).
long TtDealTimeMsc(const ulong ticket)
  {
   long msc = HistoryDealGetInteger(ticket, DEAL_TIME_MSC);
   if(msc <= 0)
      msc = HistoryDealGetInteger(ticket, DEAL_TIME) * 1000;
   return msc;
  }

// Build the deal JSON. Outputs the symbol and the UTC time (seconds).
string TtDealJson(const ulong ticket, string &symbol, long &utc)
  {
   symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
   int digits = TtSymbolDigits(symbol);
   long type  = HistoryDealGetInteger(ticket, DEAL_TYPE);
   long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
   utc = TtServerToUtc(TtDealTimeMsc(ticket) / 1000);

   string j = "{";
   j += "\"ticket\":"       + TtQ(IntegerToString((long)ticket));
   j += ",\"order\":"       + TtQ(IntegerToString(HistoryDealGetInteger(ticket, DEAL_ORDER)));
   j += ",\"position_id\":" + TtQ(IntegerToString(HistoryDealGetInteger(ticket, DEAL_POSITION_ID)));
   j += ",\"symbol\":"      + TtQ(symbol);
   j += ",\"entry\":"       + TtQ(TtDealEntryName(entry));
   j += ",\"type\":"        + TtQ(type == DEAL_TYPE_BUY ? "buy" : "sell");
   j += ",\"volume\":"      + TtQ(TtVolume(HistoryDealGetDouble(ticket, DEAL_VOLUME), symbol));
   j += ",\"price\":"       + TtQ(TtPrice(HistoryDealGetDouble(ticket, DEAL_PRICE), digits));
   j += ",\"time\":"        + IntegerToString(utc);
   j += ",\"commission\":"  + TtQ(TtMoney(HistoryDealGetDouble(ticket, DEAL_COMMISSION)));
   j += ",\"swap\":"        + TtQ(TtMoney(HistoryDealGetDouble(ticket, DEAL_SWAP)));
   j += ",\"fee\":"         + TtQ(TtMoney(HistoryDealGetDouble(ticket, DEAL_FEE)));
   j += ",\"profit\":"      + TtQ(TtMoney(HistoryDealGetDouble(ticket, DEAL_PROFIT)));
   j += ",\"sl\":"          + TtQ(TtPriceOrZero(HistoryDealGetDouble(ticket, DEAL_SL), digits));
   j += ",\"tp\":"          + TtQ(TtPriceOrZero(HistoryDealGetDouble(ticket, DEAL_TP), digits));
   j += ",\"magic\":"       + IntegerToString(HistoryDealGetInteger(ticket, DEAL_MAGIC));
   j += ",\"comment\":"     + TtQ(HistoryDealGetString(ticket, DEAL_COMMENT));
   j += "}";
   return j;
  }

// SL/TP of the deal that opened a position (baseline for a position the
// EA sees for the first time). Uses HistorySelectByPosition, which
// replaces the current history selection.
bool TtOpeningSlTp(const long position_id, double &sl, double &tp)
  {
   if(!HistorySelectByPosition(position_id))
      return false;
   int n = HistoryDealsTotal();
   for(int i = 0; i < n; i++)
     {
      ulong t = HistoryDealGetTicket(i);
      if(t == 0)
         continue;
      long e = HistoryDealGetInteger(t, DEAL_ENTRY);
      if(e == DEAL_ENTRY_IN || e == DEAL_ENTRY_INOUT)
        {
         sl = HistoryDealGetDouble(t, DEAL_SL);
         tp = HistoryDealGetDouble(t, DEAL_TP);
         return true;
        }
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Positions                                                        |
//+------------------------------------------------------------------+
struct TtPos
  {
   long              id;           // POSITION_IDENTIFIER
   string            symbol;
   long              type;         // POSITION_TYPE_BUY / POSITION_TYPE_SELL
   double            volume;
   double            price_open;
   double            sl;
   double            tp;
   long              time_srv;     // POSITION_TIME (server sec)
   long              time_msc;     // POSITION_TIME_MSC (server msc)
   long              update_msc;   // POSITION_TIME_UPDATE_MSC (server msc)
  };

// Snapshot of all open positions.
int TtReadPositions(TtPos &out[])
  {
   int total = PositionsTotal();
   ArrayResize(out, 0, total);
   int n = 0;
   for(int i = 0; i < total; i++)
     {
      ulong ticket = PositionGetTicket(i);   // also selects the position
      if(ticket == 0)
         continue;
      ArrayResize(out, n + 1, total);
      out[n].id         = PositionGetInteger(POSITION_IDENTIFIER);
      out[n].symbol     = PositionGetString(POSITION_SYMBOL);
      out[n].type       = PositionGetInteger(POSITION_TYPE);
      out[n].volume     = PositionGetDouble(POSITION_VOLUME);
      out[n].price_open = PositionGetDouble(POSITION_PRICE_OPEN);
      out[n].sl         = PositionGetDouble(POSITION_SL);
      out[n].tp         = PositionGetDouble(POSITION_TP);
      out[n].time_srv   = PositionGetInteger(POSITION_TIME);
      out[n].time_msc   = PositionGetInteger(POSITION_TIME_MSC);
      out[n].update_msc = PositionGetInteger(POSITION_TIME_UPDATE_MSC);
      n++;
     }
   return n;
  }

string TtPositionJson(const TtPos &p)
  {
   int digits = TtSymbolDigits(p.symbol);
   string j = "{";
   j += "\"position_id\":" + TtQ(IntegerToString(p.id));
   j += ",\"symbol\":"     + TtQ(p.symbol);
   j += ",\"type\":"       + TtQ(p.type == POSITION_TYPE_BUY ? "buy" : "sell");
   j += ",\"volume\":"     + TtQ(TtVolume(p.volume, p.symbol));
   j += ",\"price_open\":" + TtQ(TtPrice(p.price_open, digits));
   j += ",\"sl\":"         + TtQ(TtPriceOrZero(p.sl, digits));
   j += ",\"tp\":"         + TtQ(TtPriceOrZero(p.tp, digits));
   j += ",\"time\":"       + IntegerToString(TtServerToUtc(p.time_srv));
   j += "}";
   return j;
  }

//+------------------------------------------------------------------+
//| SL/TP modification                                               |
//+------------------------------------------------------------------+
// id = position_id:field:time_msc where time_msc is the SERVER-time
// POSITION_TIME_UPDATE_MSC — independent of the UTC offset, so the id
// is identical whether the change is seen via OnTradeTransaction, the
// 1 s poll, or after an EA restart.
string TtModJson(const long position_id, const string symbol, const string field,
                 const double old_v, const double new_v, const long update_msc_srv)
  {
   int digits = TtSymbolDigits(symbol);
   string pid = IntegerToString(position_id);
   string j = "{";
   j += "\"id\":"           + TtQ(pid + ":" + field + ":" + IntegerToString(update_msc_srv));
   j += ",\"position_id\":" + TtQ(pid);
   j += ",\"field\":"       + TtQ(field);
   j += ",\"old\":"         + TtQ(TtPriceOrZero(old_v, digits));
   j += ",\"new\":"         + TtQ(TtPriceOrZero(new_v, digits));
   j += ",\"time\":"        + IntegerToString(TtServerToUtc(update_msc_srv / 1000));
   j += "}";
   return j;
  }

//+------------------------------------------------------------------+
//| OHLC                                                             |
//+------------------------------------------------------------------+
string TtTfName(const ENUM_TIMEFRAMES tf)
  {
   switch(tf)
     {
      case PERIOD_M1:  return "M1";
      case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H4:  return "H4";
      case PERIOD_D1:  return "D1";
      default:         return "";
     }
  }

bool TtTfFromName(const string name, ENUM_TIMEFRAMES &tf)
  {
   if(name == "M1")  { tf = PERIOD_M1;  return true; }
   if(name == "M5")  { tf = PERIOD_M5;  return true; }
   if(name == "M15") { tf = PERIOD_M15; return true; }
   if(name == "M30") { tf = PERIOD_M30; return true; }
   if(name == "H1")  { tf = PERIOD_H1;  return true; }
   if(name == "H4")  { tf = PERIOD_H4;  return true; }
   if(name == "D1")  { tf = PERIOD_D1;  return true; }
   return false;
  }

// {"symbol":..,"timeframe":..,"bars":[[t,"o","h","l","c","v"],...]} for rates[start .. start+count-1]
// (rates must be in chronological order, i.e. not as-series).
string TtOhlcJson(const string sym, const string tf_name, const MqlRates &rates[], const int start, const int count)
  {
   int digits = TtSymbolDigits(sym);
   string j = "{\"symbol\":" + TtQ(sym) + ",\"timeframe\":" + TtQ(tf_name) + ",\"bars\":[";
   for(int i = start; i < start + count; i++)
     {
      if(i > start)
         j += ",";
      j += "[" + IntegerToString(TtServerToUtc((long)rates[i].time))
           + ",\"" + TtPrice(rates[i].open, digits)
           + "\",\"" + TtPrice(rates[i].high, digits)
           + "\",\"" + TtPrice(rates[i].low, digits)
           + "\",\"" + TtPrice(rates[i].close, digits)
           + "\",\"" + IntegerToString(rates[i].tick_volume) + "\"]";
     }
   j += "]}";
   return j;
  }

#endif // TT_COLLECT_MQH
