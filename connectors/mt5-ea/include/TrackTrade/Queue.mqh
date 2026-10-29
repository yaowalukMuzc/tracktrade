//+------------------------------------------------------------------+
//| TrackTrade/Queue.mqh                                             |
//| File-backed FIFO of unsent items: MQL5/Files/TrackTrade/<login>.queue
//|                                                                  |
//| One item per line, TAB-separated (JSON fragments never contain a |
//| raw TAB/CR/LF because Json.mqh escapes control characters):      |
//|   D <TAB> symbol <TAB> utc_time <TAB> {deal json}                |
//|   M <TAB> symbol <TAB> utc_time <TAB> {modification json}        |
//|   O <TAB> symbol <TAB> bar_count <TAB> {ohlc json}               |
//|   H <TAB> from <TAB> to <TAB> final(0/1) <TAB> n                 |
//|     -> history-import chunk header; the next n lines are its D   |
//|        items and are sent together with "history":{...}.         |
//| The file is UTF-8 text (FILE_ANSI + CP_UTF8).                    |
//+------------------------------------------------------------------+
#ifndef TT_QUEUE_MQH
#define TT_QUEUE_MQH

#define TT_FILE_FLAGS_READ  (FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ)
#define TT_FILE_FLAGS_WRITE (FILE_WRITE | FILE_TXT | FILE_ANSI)

// Write all lines to `file` atomically (temp file + FileMove).
bool TtWriteLinesAtomic(const string file, const string &lines[], const int from, const int to)
  {
   string tmp = file + ".tmp";
   int h = FileOpen(tmp, TT_FILE_FLAGS_WRITE, '\t', CP_UTF8);
   if(h == INVALID_HANDLE)
     {
      PrintFormat("TrackTrade: cannot write %s (error %d)", tmp, GetLastError());
      return false;
     }
   for(int i = from; i < to; i++)
      FileWriteString(h, lines[i] + "\r\n");
   FileFlush(h);
   FileClose(h);
   if(!FileMove(tmp, 0, file, FILE_REWRITE))
     {
      PrintFormat("TrackTrade: cannot replace %s (error %d)", file, GetLastError());
      return false;
     }
   return true;
  }

class CTtQueue
  {
private:
   string            m_file;     // path relative to MQL5/Files
   string            m_lines[];
   int               m_head;     // index of the first unsent line
   int               m_size;     // number of used slots in m_lines

   void              Compact(void)
     {
      if(m_head == 0)
         return;
      int n = m_size - m_head;
      for(int i = 0; i < n; i++)
         m_lines[i] = m_lines[m_head + i];
      m_size = n;
      m_head = 0;
      ArrayResize(m_lines, m_size, 1024);
     }

   void              AppendMem(const string line)
     {
      ArrayResize(m_lines, m_size + 1, 1024);
      m_lines[m_size] = line;
      m_size++;
     }

public:
                     CTtQueue(void) { m_file = ""; m_head = 0; m_size = 0; }

   // Load the queue from disk (missing file = empty queue).
   bool              Load(const string file)
     {
      m_file = file;
      m_head = 0;
      m_size = 0;
      ArrayResize(m_lines, 0, 1024);
      if(!FileIsExist(m_file))
         return true;
      int h = FileOpen(m_file, TT_FILE_FLAGS_READ, '\t', CP_UTF8);
      if(h == INVALID_HANDLE)
        {
         PrintFormat("TrackTrade: cannot read %s (error %d)", m_file, GetLastError());
         return false;
        }
      while(!FileIsEnding(h))
        {
         string line = FileReadString(h);
         if(StringLen(line) < 3)
            continue;
         ushort k = StringGetCharacter(line, 0);
         if((k == 'D' || k == 'M' || k == 'O' || k == 'H') && StringGetCharacter(line, 1) == 9)
            AppendMem(line);
        }
      FileClose(h);
      return true;
     }

   int               Count(void) { return m_size - m_head; }

   string            At(const int i) { return m_lines[m_head + i]; }

   void              Set(const int i, const string line) { m_lines[m_head + i] = line; }

   // Insert a line before relative index i (in memory; call Save()).
   void              Insert(const int i, const string line)
     {
      Compact();
      ArrayResize(m_lines, m_size + 1, 1024);
      for(int k = m_size; k > i; k--)
         m_lines[k] = m_lines[k - 1];
      m_lines[i] = line;
      m_size++;
     }

   // Append lines in memory and to the end of the file.
   bool              Push(const string &lines[], const int n)
     {
      if(n <= 0)
         return true;
      for(int i = 0; i < n; i++)
         AppendMem(lines[i]);
      int h = FileOpen(m_file, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ, '\t', CP_UTF8);
      if(h == INVALID_HANDLE)
        {
         PrintFormat("TrackTrade: cannot append to %s (error %d)", m_file, GetLastError());
         return Save();
        }
      FileSeek(h, 0, SEEK_END);
      for(int i = 0; i < n; i++)
         FileWriteString(h, lines[i] + "\r\n");
      FileFlush(h);
      FileClose(h);
      return true;
     }

   bool              PushOne(const string line)
     {
      string one[1];
      one[0] = line;
      return Push(one, 1);
     }

   // Drop the first n lines (after the server accepted them) and persist.
   bool              RemoveHead(const int n)
     {
      int k = MathMin(n, Count());
      if(k <= 0)
         return true;
      for(int i = 0; i < k; i++)
         m_lines[m_head + i] = "";     // release memory early
      m_head += k;
      return Save();
     }

   // Rewrite the whole file (compacted).
   bool              Save(void)
     {
      if(m_file == "")
         return false;
      Compact();
      return TtWriteLinesAtomic(m_file, m_lines, 0, m_size);
     }
  };

#endif // TT_QUEUE_MQH
