//+------------------------------------------------------------------+
//| TrackTrade/Http.mqh                                              |
//| Thin wrapper around WebRequest(): UTF-8 body, status, response   |
//| headers, Retry-After and round-trip time.                        |
//+------------------------------------------------------------------+
#ifndef TT_HTTP_MQH
#define TT_HTTP_MQH

// GetLastError() after WebRequest() returns -1 when the URL is not in
// Tools › Options › Expert Advisors › "Allow WebRequest for listed URL".
#define TT_ERR_WEBREQUEST_NOT_ALLOWED 4014

struct TtHttpResult
  {
   int               status;       // HTTP status, or -1 when WebRequest itself failed
   int               error;        // GetLastError() when status == -1
   string            body;         // response body (UTF-8 decoded)
   string            headers;      // raw response headers
   int               retry_after;  // seconds from the Retry-After header (0 = absent)
   uint              rtt_ms;       // round-trip time
  };

// Parse "Retry-After: <seconds>" (case-insensitive) out of raw headers.
// HTTP-date values are not supported (the API sends seconds) -> 0.
int TtParseRetryAfter(const string headers)
  {
   string lines[];
   int n = StringSplit(headers, (ushort)10, lines);   // split on LF, CR is trimmed below
   for(int i = 0; i < n; i++)
     {
      string line = lines[i];
      StringTrimLeft(line);
      StringTrimRight(line);
      string low = line;
      StringToLower(low);
      if(StringFind(low, "retry-after:") == 0)
        {
         string v = StringSubstr(line, 12);
         StringTrimLeft(v);
         StringTrimRight(v);
         long secs = StringToInteger(v);
         if(secs < 0)
            secs = 0;
         if(secs > 3600)
            secs = 3600;
         return (int)secs;
        }
     }
   return 0;
  }

// POST a JSON body. Always fills `res`; returns true when an HTTP
// response was received (any status), false on transport failure.
bool TtHttpPostJson(const string url, const string api_key, const string body,
                    const int timeout_ms, const string user_agent, TtHttpResult &res)
  {
   char data[];
   char result[];
   string result_headers = "";

   //--- body -> UTF-8 bytes, without the terminating NUL that StringToCharArray appends
   int n = StringToCharArray(body, data, 0, WHOLE_ARRAY, CP_UTF8);
   if(n > 0)
      ArrayResize(data, n - 1);

   string headers = "Content-Type: application/json\r\n"
                    + "Accept: application/json\r\n"
                    + "X-Api-Key: " + api_key + "\r\n"
                    + "User-Agent: " + user_agent + "\r\n";

   ResetLastError();
   uint t0 = GetTickCount();
   int status = WebRequest("POST", url, headers, timeout_ms, data, result, result_headers);
   res.rtt_ms      = GetTickCount() - t0;
   res.status      = status;
   res.error       = (status == -1) ? GetLastError() : 0;
   res.headers     = result_headers;
   res.body        = (ArraySize(result) > 0) ? CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8) : "";
   res.retry_after = (status == -1) ? 0 : TtParseRetryAfter(result_headers);
   return (status != -1);
  }

#endif // TT_HTTP_MQH
