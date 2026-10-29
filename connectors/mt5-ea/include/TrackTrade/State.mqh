//+------------------------------------------------------------------+
//| TrackTrade/State.mqh                                             |
//| Persistent EA state: MQL5/Files/TrackTrade/<login>.state         |
//|                                                                  |
//| Plain "key=value" lines:                                         |
//|   version=1                                                      |
//|   history_done=1          first-run 90-day import was queued     |
//|   last_deal_msc=...       newest queued deal, SERVER time msc    |
//|   saved_srv=...           server time (sec) of the last save     |
//|   pos=<id>;<sl>;<tp>;<update_msc>   last known SL/TP per open position
//+------------------------------------------------------------------+
#ifndef TT_STATE_MQH
#define TT_STATE_MQH

#include "Queue.mqh"   // TtWriteLinesAtomic, TT_FILE_FLAGS_READ

struct TtPosState
  {
   long              id;           // POSITION_IDENTIFIER
   double            sl;
   double            tp;
   long              update_msc;   // POSITION_TIME_UPDATE_MSC (server time)
  };

class CTtState
  {
public:
   bool              history_done;
   long              last_deal_msc;
   long              saved_srv;
   TtPosState        pos[];

                     CTtState(void) { Reset(); }

   void              Reset(void)
     {
      history_done  = false;
      last_deal_msc = 0;
      saved_srv     = 0;
      ArrayResize(pos, 0);
     }

   // Returns true if the state file existed and was read.
   bool              Load(const string file)
     {
      Reset();
      if(!FileIsExist(file))
         return false;
      int h = FileOpen(file, TT_FILE_FLAGS_READ, '\t', CP_UTF8);
      if(h == INVALID_HANDLE)
        {
         PrintFormat("TrackTrade: cannot read %s (error %d)", file, GetLastError());
         return false;
        }
      while(!FileIsEnding(h))
        {
         string line = FileReadString(h);
         int eq = StringFind(line, "=");
         if(eq <= 0)
            continue;
         string key = StringSubstr(line, 0, eq);
         string val = StringSubstr(line, eq + 1);
         if(key == "history_done")
            history_done = (val == "1");
         else if(key == "last_deal_msc")
            last_deal_msc = StringToInteger(val);
         else if(key == "saved_srv")
            saved_srv = StringToInteger(val);
         else if(key == "pos")
           {
            string f[];
            if(StringSplit(val, (ushort)';', f) == 4)
               Upsert(StringToInteger(f[0]), StringToDouble(f[1]), StringToDouble(f[2]), StringToInteger(f[3]));
           }
        }
      FileClose(h);
      return true;
     }

   bool              Save(const string file)
     {
      saved_srv = (long)TimeTradeServer();
      int n = ArraySize(pos);
      string lines[];
      ArrayResize(lines, 4 + n);
      lines[0] = "version=1";
      lines[1] = "history_done=" + (history_done ? "1" : "0");
      lines[2] = "last_deal_msc=" + IntegerToString(last_deal_msc);
      lines[3] = "saved_srv=" + IntegerToString(saved_srv);
      for(int i = 0; i < n; i++)
         lines[4 + i] = "pos=" + IntegerToString(pos[i].id) + ";"
                        + DoubleToString(pos[i].sl, 8) + ";"
                        + DoubleToString(pos[i].tp, 8) + ";"
                        + IntegerToString(pos[i].update_msc);
      return TtWriteLinesAtomic(file, lines, 0, 4 + n);
     }

   int               Find(const long id)
     {
      int n = ArraySize(pos);
      for(int i = 0; i < n; i++)
         if(pos[i].id == id)
            return i;
      return -1;
     }

   void              Upsert(const long id, const double sl, const double tp, const long update_msc)
     {
      int i = Find(id);
      if(i < 0)
        {
         i = ArraySize(pos);
         ArrayResize(pos, i + 1);
         pos[i].id = id;
        }
      pos[i].sl         = sl;
      pos[i].tp         = tp;
      pos[i].update_msc = update_msc;
     }

   void              RemoveAt(const int i)
     {
      int n = ArraySize(pos);
      if(i < 0 || i >= n)
         return;
      for(int k = i; k < n - 1; k++)
         pos[k] = pos[k + 1];
      ArrayResize(pos, n - 1);
     }
  };

#endif // TT_STATE_MQH
