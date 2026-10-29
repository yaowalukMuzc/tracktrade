# TrackTrade MT5 Expert Advisor

[ภาษาไทย](#ภาษาไทย) · [English](#english)

---

## ภาษาไทย

### EA นี้ทำอะไร
`TrackTrade.mq5` ทำงานใน MetaTrader 5 ของคุณ และส่งข้อมูลการเทรดเข้า TrackTrade อัตโนมัติ เทรดจะขึ้นในเจอร์นัลภายในประมาณ 5 วินาที

- ส่ง **deal** ทุกครั้งที่เปิด/ปิด/ปิดบางส่วน (เฉพาะ Buy/Sell — ไม่ส่งรายการฝาก/ถอน/เครดิต)
- ส่ง **การแก้ SL/TP** ของ position ที่เปิดอยู่
- ส่ง **snapshot ของ position ที่เปิดอยู่ + balance/equity** ทุก 10 วินาที (heartbeat)
- ส่ง **สเปกของสัญลักษณ์** (digits, contract size, tick value …) เพื่อคำนวณ R และ $ ได้ถูกต้อง
- ส่ง **แท่งราคา (OHLC M1–D1)** รอบเทรด เมื่อแอปร้องขอ
- ครั้งแรกที่ติดตั้ง จะนำเข้า **ประวัติย้อนหลัง 90 วัน** ให้อัตโนมัติ
- ถ้าเน็ตหลุด ข้อมูลจะถูกเก็บในคิวไฟล์และส่งซ้ำเองเมื่อกลับมาออนไลน์ (เซิร์ฟเวอร์ตัดข้อมูลซ้ำให้)

EA **ไม่เปิด ไม่ปิด และไม่แก้ออเดอร์ใด ๆ** — อ่านข้อมูลอย่างเดียว

### ติดตั้ง
1. **คัดลอกไฟล์** — ใน MT5 เปิด *File › Open Data Folder* แล้ว
   - คัดลอก `TrackTrade.mq5` ไปที่ `MQL5/Experts/`
   - คัดลอกโฟลเดอร์ `include/TrackTrade` ไปเป็น `MQL5/Include/TrackTrade` (ต้องได้ `MQL5/Include/TrackTrade/Json.mqh` ฯลฯ)
2. **คอมไพล์** — เปิด `TrackTrade.mq5` ใน MetaEditor แล้วกด *Compile* (F7)
   (หรือถ้าได้ไฟล์ `TrackTrade.ex5` มาแล้ว ให้คัดลอกไปที่ `MQL5/Experts/` ได้เลย ไม่ต้องคอมไพล์)
3. **อนุญาต WebRequest** — *Tools › Options › Expert Advisors* → ติ๊ก **Allow WebRequest for listed URL** แล้วกดเพิ่ม URL ของแอป เช่น `https://app.tracktrade.example`
4. **เปิด Algo Trading** — ปุ่ม *Algo Trading* บนแถบเครื่องมือต้องเป็นสีเขียว
5. **ลาก EA ใส่กราฟใดก็ได้ 1 กราฟต่อบัญชี** (สัญลักษณ์/ไทม์เฟรมไม่มีผล)
6. ในแท็บ *Inputs* ใส่
   - `ApiUrl` — URL ของแอป (ต้องตรงกับที่เพิ่มในข้อ 3)
   - `ApiKey` — คัดลอกจากแอป หน้า **Accounts › การเชื่อมต่อ** (ขึ้นต้นด้วย `tt_live_`)
   - `HistoryDays` (90), `HeartbeatSec` (10), `OhlcBarsAround` (200) — ปกติไม่ต้องแก้
7. กด OK — มุมซ้ายบนของกราฟจะแสดงสถานะ

### สถานะบนกราฟ
| บรรทัด | ความหมาย |
|---|---|
| `สถานะ / Status: เชื่อมต่อแล้ว / connected` | ส่งข้อมูลสำเร็จล่าสุดแล้ว |
| `กำลังเชื่อมต่อ… / connecting…` | ยังไม่เคยส่งสำเร็จในรอบนี้ |
| `รอเทอร์มินัลเชื่อมต่อโบรกเกอร์` | MT5 ยังไม่ล็อกอินเข้าเซิร์ฟเวอร์โบรกเกอร์ |
| `ออฟไลน์ ลองใหม่ใน N วิ / offline, retry in N s` | ส่งไม่สำเร็จ กำลังรอส่งใหม่ (1, 2, 4 … สูงสุด 60 วินาที) |
| `ซิงก์ล่าสุด / Last sync` | เวลา (UTC) ที่ส่งสำเร็จล่าสุด และเวลาตอบกลับ (ms) |
| `รอส่ง / Queued` | จำนวนรายการที่ยังค้างในคิว (ควรเป็น 0 เกือบตลอดเวลา) |
| `สัญลักษณ์ที่ยังไม่แมป` | สัญลักษณ์ของโบรกเกอร์ที่แอปยังจับคู่ไม่ได้ — เพิ่ม mapping ในแอป |
| `ข้อผิดพลาดล่าสุด / Last error` | ข้อผิดพลาดล่าสุด (ดูรายละเอียดเพิ่มในแท็บ *Experts*) |

### แก้ปัญหา
- **`API key ไม่ถูกต้อง / invalid API key`** (HTTP 401) — EA หยุดส่ง กด F7 บนกราฟ แก้ `ApiKey` ให้ตรงกับหน้า Accounts › การเชื่อมต่อ (key ถูกสร้างใหม่หรือถูกยกเลิกหรือไม่) แล้วกด OK EA จะเริ่มส่งใหม่พร้อมข้อมูลที่ค้างในคิว
- **Alert เรื่อง WebRequest / error 4014** — ยังไม่ได้เพิ่ม URL ในข้อ 3 หรือพิมพ์ไม่ตรงกับ `ApiUrl` (ต้องตรงทั้ง `https://` และชื่อโดเมน) เพิ่มแล้ว EA จะลองใหม่เองภายใน 60 วินาที
- **ไม่มีอะไรเข้าแอปเลย**
  - มุมขวาบนของกราฟมีหน้ายิ้ม/ไอคอน EA หรือไม่ และ Algo Trading เปิดอยู่หรือไม่
  - ดูแท็บ *Experts* และ *Journal* ในหน้าต่าง Toolbox (Ctrl+T) หา `TrackTrade:`
  - `Queued` เพิ่มขึ้นเรื่อย ๆ = ส่งไม่ออก ดู `Last error`
  - ติดตั้ง EA ไว้บน **บัญชีที่ถูกต้อง** หรือไม่ (key ผูกกับบัญชีเดียว)
  - ใช้ใน Strategy Tester ไม่ได้ — WebRequest ทำงานเฉพาะกราฟจริง
- **อยากส่งประวัติใหม่ทั้งหมด** — กด Resync ในแอป (EA จะได้คำสั่งในรอบ heartbeat ถัดไป) หรือลบไฟล์ `MQL5/Files/TrackTrade/<login>.state` แล้วรีสตาร์ต EA

### ความเป็นส่วนตัว
EA ส่ง **เฉพาะ** ข้อมูลเทรด (deals, positions, การแก้ SL/TP), สเปกสัญลักษณ์, เลขบัญชี/ชื่อเซิร์ฟเวอร์/โบรกเกอร์/สกุลเงิน, balance/equity และแท่งราคา **ไม่ส่งรหัสผ่าน** ไม่อ่านข้อมูลส่วนตัว และไม่ส่งข้อมูลอื่นในเครื่อง การเชื่อมต่อใช้ HTTPS และยืนยันตัวตนด้วย API key ของบัญชีนั้นเท่านั้น
ไฟล์ในเครื่อง: `MQL5/Files/TrackTrade/<login>.queue` (ข้อมูลที่ยังไม่ได้ส่ง) และ `<login>.state` (สถานะ EA)

### ข้อจำกัด
- **ใช้ EA 1 ตัวต่อ 1 บัญชี** — ถ้าติดหลายกราฟในบัญชีเดียวกันจะส่งซ้ำและแย่งไฟล์คิวกัน
- **บัญชี netting ที่กลับฝั่ง (DEAL_ENTRY_INOUT)** — EA ส่ง deal ตามที่ MT5 รายงาน (`entry: "inout"`) การแยกเป็นปิด position เดิม + เปิด position ใหม่ทำที่ฝั่งเซิร์ฟเวอร์
- เวลาถูกแปลงเป็น UTC ด้วย offset ของเซิร์ฟเวอร์ **ปัจจุบัน** — deal เก่าในประวัติที่ข้ามช่วงเปลี่ยน daylight saving อาจคลาดไป 1 ชั่วโมง
- ถ้าแก้ SL/TP หลายครั้งภายใน 1 วินาทีขณะไม่มี event ส่งมา EA อาจเห็นแค่ค่าล่าสุด
- สำหรับสัญลักษณ์ที่ไม่อยู่ใน Market Watch EA จะเพิ่มเข้า Market Watch ให้ (เพื่ออ่าน tick value และแท่งราคา)

---

## English

### What it does
`TrackTrade.mq5` runs inside your MetaTrader 5 terminal and pushes your trading activity to TrackTrade, so trades show up in the journal within about 5 seconds.

- Sends every **deal** (open / close / partial close — buy/sell deals only, no balance/credit entries)
- Sends **SL/TP changes** of open positions
- Sends an **open-positions snapshot + balance/equity** every 10 s (heartbeat)
- Sends each **symbol's spec** (digits, contract size, tick value …) so R and $ are computed correctly
- Sends **price bars (OHLC M1–D1)** around trades when the app asks for them
- On first install it **imports the last 90 days** of history
- When the network is down, items stay in a file queue and are re-sent automatically (the server de-duplicates)

The EA **never opens, closes or modifies orders** — it is read-only.

### Install
1. **Copy the files** — in MT5 use *File › Open Data Folder*, then
   - copy `TrackTrade.mq5` to `MQL5/Experts/`
   - copy the folder `include/TrackTrade` to `MQL5/Include/TrackTrade` (you should have `MQL5/Include/TrackTrade/Json.mqh` etc.)
2. **Compile** — open `TrackTrade.mq5` in MetaEditor and press *Compile* (F7)
   (or, if you were given `TrackTrade.ex5`, just copy it to `MQL5/Experts/`)
3. **Allow WebRequest** — *Tools › Options › Expert Advisors* → tick **Allow WebRequest for listed URL** and add the app URL, e.g. `https://app.tracktrade.example`
4. **Enable Algo Trading** — the *Algo Trading* toolbar button must be green
5. **Attach the EA to any one chart per account** (symbol/timeframe don't matter)
6. In the *Inputs* tab set
   - `ApiUrl` — the app URL (must match the one added in step 3)
   - `ApiKey` — copy it from the app, **Accounts › Connections** (starts with `tt_live_`)
   - `HistoryDays` (90), `HeartbeatSec` (10), `OhlcBarsAround` (200) — normally leave as is
7. Press OK — the status appears in the chart's top-left corner

### Chart status
| Line | Meaning |
|---|---|
| `Status: connected` | the last request succeeded |
| `connecting…` | nothing sent successfully yet in this session |
| `waiting for the terminal to connect` | MT5 is not logged in to the broker server yet |
| `offline, retry in N s` | sending failed; retrying with backoff (1, 2, 4 … max 60 s) |
| `Last sync` | time (UTC) of the last successful request and its round-trip time |
| `Queued` | items still waiting in the queue (should be 0 almost always) |
| `Unmapped symbols` | broker symbols the app could not map — add a mapping in the app |
| `Last error` | most recent error (more detail in the *Experts* tab) |

### Troubleshooting
- **`invalid API key`** (HTTP 401) — the EA stops sending. Press F7 on the chart, fix `ApiKey` (was the key regenerated or revoked on Accounts › Connections?) and press OK; it resumes and sends what was queued.
- **WebRequest alert / error 4014** — the URL from step 3 is missing or doesn't match `ApiUrl` exactly (scheme and host). Once added, the EA retries by itself within 60 s.
- **Nothing arrives in the app**
  - is the EA icon shown top-right on the chart, and is Algo Trading on?
  - check the *Experts* and *Journal* tabs of the Toolbox (Ctrl+T) for `TrackTrade:` lines
  - `Queued` keeps growing = requests fail; see `Last error`
  - is the EA running on the **right account**? (a key belongs to one account)
  - it does not work in the Strategy Tester — WebRequest is only available on live charts
- **Re-send all history** — press Resync in the app (the EA receives the command on its next heartbeat), or delete `MQL5/Files/TrackTrade/<login>.state` and restart the EA.

### Privacy
The EA sends **only** trading data (deals, positions, SL/TP changes), symbol specs, account number/server/broker/currency, balance/equity and price bars. **No passwords**, no personal data, nothing else from your computer. Traffic is HTTPS, authenticated by that account's API key.
Local files: `MQL5/Files/TrackTrade/<login>.queue` (unsent items) and `<login>.state` (EA state).

### Limits
- **One EA per account** — attaching it to several charts of the same account duplicates traffic and fights over the queue file.
- **Netting reversals (`DEAL_ENTRY_INOUT`)** are sent exactly as MT5 reports them (`entry: "inout"`); splitting them into "close old + open new position" is done server-side.
- Times are converted to UTC with the broker's **current** offset — old history deals on the other side of a daylight-saving switch may be off by one hour.
- Several SL/TP edits within one second with no trade event in between may be reported as a single change.
- Symbols not in Market Watch are added to it (needed to read tick value and price bars).

---

### For developers
- Wire contract: [`PROTOCOL.md`](PROTOCOL.md)
- Source layout: `TrackTrade.mq5` (event loop, batching, retry, commands) + `include/TrackTrade/`
  `Json.mqh` (escaping + minimal parser) · `Http.mqh` (WebRequest wrapper) · `Queue.mqh` (file queue) · `State.mqh` (state file) · `Collect.mqh` (MT5 → JSON)
- Manual API testing without MT5: `python tools/mock_ea.py --url http://localhost:8001 --key tt_live_… open|close|modify-sl|history|heartbeat|duplicate`
