//+------------------------------------------------------------------+
//| TrackTrade/Json.mqh                                              |
//| JSON string escaping for the request builder and a minimal       |
//| recursive-descent parser, good enough to read the API response   |
//| (`accepted`, `duplicates`, `unknown_symbols`, `commands`, `code`).|
//+------------------------------------------------------------------+
#ifndef TT_JSON_MQH
#define TT_JSON_MQH

//+------------------------------------------------------------------+
//| Escaping                                                         |
//+------------------------------------------------------------------+
// Escape a string for use inside a JSON string literal.
// Non-ASCII characters are kept as-is (the body is converted to UTF-8
// right before sending). Control characters become \n, \t, \uXXXX …
// so a JSON fragment never contains a raw TAB / CR / LF — the file
// queue relies on that (it is TAB-separated, one item per line).
string TtJsonEscape(const string s)
  {
   int n = StringLen(s);
   //--- fast path: nothing to escape
   bool clean = true;
   for(int i = 0; i < n; i++)
     {
      ushort c = StringGetCharacter(s, i);
      if(c < 32 || c == 34 || c == 92)
        {
         clean = false;
         break;
        }
     }
   if(clean)
      return s;

   string out = "";
   for(int i = 0; i < n; i++)
     {
      ushort c = StringGetCharacter(s, i);
      if(c == 34)
         out += "\\\"";
      else if(c == 92)
         out += "\\\\";
      else if(c == 10)
         out += "\\n";
      else if(c == 13)
         out += "\\r";
      else if(c == 9)
         out += "\\t";
      else if(c == 8)
         out += "\\b";
      else if(c == 12)
         out += "\\f";
      else if(c < 32)
         out += StringFormat("\\u%04X", (int)c);
      else
         out += ShortToString(c);
     }
   return out;
  }

// Quote + escape: TtQ("a\"b") -> "\"a\\\"b\""
string TtQ(const string s)
  {
   return "\"" + TtJsonEscape(s) + "\"";
  }

//+------------------------------------------------------------------+
//| Parsed value tree                                                |
//+------------------------------------------------------------------+
enum ENUM_TTJ_TYPE
  {
   TTJ_NULL = 0,
   TTJ_BOOL,
   TTJ_NUMBER,
   TTJ_STRING,
   TTJ_ARRAY,
   TTJ_OBJECT
  };

class CTtJson
  {
public:
   ENUM_TTJ_TYPE     m_type;
   string            m_value;      // decoded text for strings, raw literal for numbers/bools
   string            m_keys[];     // object keys, parallel to m_items (empty for arrays)
   CTtJson          *m_items[];    // children (array elements or object values)

                     CTtJson(void) { m_type = TTJ_NULL; m_value = ""; }
                    ~CTtJson(void) { Clear(); }

   void              Clear(void)
     {
      int n = ArraySize(m_items);
      for(int i = 0; i < n; i++)
         if(CheckPointer(m_items[i]) == POINTER_DYNAMIC)
            delete m_items[i];
      ArrayResize(m_items, 0);
      ArrayResize(m_keys, 0);
     }

   void              Add(const string key, CTtJson *child)
     {
      int n = ArraySize(m_items);
      ArrayResize(m_items, n + 1);
      ArrayResize(m_keys, n + 1);
      m_items[n] = child;
      m_keys[n]  = key;
     }

   int               Size(void) { return ArraySize(m_items); }

   CTtJson          *At(const int i)
     {
      if(i < 0 || i >= ArraySize(m_items))
         return NULL;
      return m_items[i];
     }

   // Object member lookup (NULL if missing or not an object).
   CTtJson          *Get(const string key)
     {
      if(m_type != TTJ_OBJECT)
         return NULL;
      int n = ArraySize(m_items);
      for(int i = 0; i < n; i++)
         if(m_keys[i] == key)
            return m_items[i];
      return NULL;
     }

   string            Str(const string key, const string def = "")
     {
      CTtJson *v = Get(key);
      if(v == NULL || v.m_type == TTJ_NULL || v.m_type == TTJ_ARRAY || v.m_type == TTJ_OBJECT)
         return def;
      return v.m_value;
     }

   long              Long(const string key, const long def = 0)
     {
      CTtJson *v = Get(key);
      if(v == NULL || (v.m_type != TTJ_NUMBER && v.m_type != TTJ_STRING) || v.m_value == "")
         return def;
      return StringToInteger(v.m_value);
     }
  };

//+------------------------------------------------------------------+
//| Parser                                                           |
//+------------------------------------------------------------------+
int TtHexVal(const ushort c)
  {
   if(c >= 48 && c <= 57)
      return (int)c - 48;        // 0-9
   if(c >= 97 && c <= 102)
      return (int)c - 97 + 10;   // a-f
   if(c >= 65 && c <= 70)
      return (int)c - 65 + 10;   // A-F
   return -1;
  }

class CTtJsonParser
  {
private:
   string            m_s;
   int               m_pos;
   int               m_len;

   ushort            Peek(void)
     {
      if(m_pos < m_len)
         return StringGetCharacter(m_s, m_pos);
      return 0;
     }

   void              SkipWs(void)
     {
      while(m_pos < m_len)
        {
         ushort c = StringGetCharacter(m_s, m_pos);
         if(c == 32 || c == 9 || c == 10 || c == 13)
            m_pos++;
         else
            break;
        }
     }

   bool              ParseString(string &out)
     {
      out = "";
      if(Peek() != 34)   // "
         return false;
      m_pos++;
      int seg = m_pos;
      while(m_pos < m_len)
        {
         ushort c = StringGetCharacter(m_s, m_pos);
         if(c == 34)
           {
            if(m_pos > seg)
               out += StringSubstr(m_s, seg, m_pos - seg);
            m_pos++;
            return true;
           }
         if(c == 92)     // backslash
           {
            if(m_pos > seg)
               out += StringSubstr(m_s, seg, m_pos - seg);
            m_pos++;
            if(m_pos >= m_len)
               return false;
            ushort e = StringGetCharacter(m_s, m_pos);
            m_pos++;
            if(e == 34)
               out += "\"";
            else if(e == 92)
               out += "\\";
            else if(e == 47)
               out += "/";
            else if(e == 98)
               out += ShortToString(8);    // \b
            else if(e == 102)
               out += ShortToString(12);   // \f
            else if(e == 110)
               out += "\n";
            else if(e == 114)
               out += "\r";
            else if(e == 116)
               out += "\t";
            else if(e == 117)                // \uXXXX (surrogate pairs are appended unit by unit — MQL strings are UTF-16)
              {
               if(m_pos + 4 > m_len)
                  return false;
               int code = 0;
               for(int k = 0; k < 4; k++)
                 {
                  int h = TtHexVal(StringGetCharacter(m_s, m_pos + k));
                  if(h < 0)
                     return false;
                  code = code * 16 + h;
                 }
               m_pos += 4;
               out += ShortToString((ushort)code);
              }
            else
               return false;
            seg = m_pos;
            continue;
           }
         m_pos++;
        }
      return false;   // unterminated
     }

   CTtJson          *ParseValue(const int depth)
     {
      if(depth > 64)
         return NULL;
      SkipWs();
      ushort c = Peek();

      //--- object
      if(c == 123)   // {
        {
         CTtJson *obj = new CTtJson();
         obj.m_type = TTJ_OBJECT;
         m_pos++;
         SkipWs();
         if(Peek() == 125)   // }
           {
            m_pos++;
            return obj;
           }
         while(true)
           {
            SkipWs();
            string key;
            if(!ParseString(key))
              {
               delete obj;
               return NULL;
              }
            SkipWs();
            if(Peek() != 58)   // :
              {
               delete obj;
               return NULL;
              }
            m_pos++;
            CTtJson *v = ParseValue(depth + 1);
            if(v == NULL)
              {
               delete obj;
               return NULL;
              }
            obj.Add(key, v);
            SkipWs();
            ushort d = Peek();
            if(d == 44)   // ,
              {
               m_pos++;
               continue;
              }
            if(d == 125)  // }
              {
               m_pos++;
               return obj;
              }
            delete obj;
            return NULL;
           }
        }

      //--- array
      if(c == 91)   // [
        {
         CTtJson *arr = new CTtJson();
         arr.m_type = TTJ_ARRAY;
         m_pos++;
         SkipWs();
         if(Peek() == 93)   // ]
           {
            m_pos++;
            return arr;
           }
         while(true)
           {
            CTtJson *v = ParseValue(depth + 1);
            if(v == NULL)
              {
               delete arr;
               return NULL;
              }
            arr.Add("", v);
            SkipWs();
            ushort d = Peek();
            if(d == 44)
              {
               m_pos++;
               continue;
              }
            if(d == 93)
              {
               m_pos++;
               return arr;
              }
            delete arr;
            return NULL;
           }
        }

      //--- string
      if(c == 34)
        {
         string s;
         if(!ParseString(s))
            return NULL;
         CTtJson *str = new CTtJson();
         str.m_type  = TTJ_STRING;
         str.m_value = s;
         return str;
        }

      //--- literals
      if(StringSubstr(m_s, m_pos, 4) == "true")
        {
         m_pos += 4;
         CTtJson *b = new CTtJson();
         b.m_type  = TTJ_BOOL;
         b.m_value = "true";
         return b;
        }
      if(StringSubstr(m_s, m_pos, 5) == "false")
        {
         m_pos += 5;
         CTtJson *b = new CTtJson();
         b.m_type  = TTJ_BOOL;
         b.m_value = "false";
         return b;
        }
      if(StringSubstr(m_s, m_pos, 4) == "null")
        {
         m_pos += 4;
         return new CTtJson();
        }

      //--- number: - + . 0-9 e E
      int start = m_pos;
      while(m_pos < m_len)
        {
         ushort d = StringGetCharacter(m_s, m_pos);
         if((d >= 48 && d <= 57) || d == 45 || d == 43 || d == 46 || d == 101 || d == 69)
            m_pos++;
         else
            break;
        }
      if(m_pos == start)
         return NULL;
      CTtJson *num = new CTtJson();
      num.m_type  = TTJ_NUMBER;
      num.m_value = StringSubstr(m_s, start, m_pos - start);
      return num;
     }

public:
   // Parse a complete JSON text. Returns NULL on error. The caller owns
   // (and must `delete`) the returned tree.
   CTtJson          *Parse(const string text)
     {
      m_s   = text;
      m_pos = 0;
      m_len = StringLen(text);
      CTtJson *root = ParseValue(0);
      return root;
     }
  };

#endif // TT_JSON_MQH
