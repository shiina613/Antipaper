# Tiáº¿n Ä‘á»™ hiá»‡n táº¡i

**Cáº­p nháº­t:** 18/07/2026
**Baseline:** nhÃ¡nh `tuan`, commit `ac624f3`

File nÃ y chá»‰ ghi nháº­n viá»‡c Ä‘Ã£ lÃ m, Ä‘ang lÃ m vÃ  chÆ°a lÃ m. Káº¿ hoáº¡ch náº±m trong `BUILD_PLAN_48H.md`; phÃ¢n cÃ´ng náº±m trong cÃ¡c file `TASKS_*.md`.

## ÄÃ£ lÃ m

| Háº¡ng má»¥c | Báº±ng chá»©ng | Ghi chÃº |
|---|---|---|
| Khung xu ly PDF native | `backend/pipeline/` | Co trich xuat theo trang, phat hien vung bang va ghep noi dung |
| FastAPI backend | `backend/` | Co upload, status, report, page, Q&A, cache artifact va history |
| Logic intelligence mau | `backend/intelligence/meeting_intelligence.py` | Rule-based fallback; chua phai AI production |
| Next.js dashboard | `frontend/app/page.tsx` | Co upload that, progress, report, viewer, chat va history |
| TÃ i liá»‡u PDF 40+ trang | Kho `data/` | ÄÃ£ cÃ³ nhiá»u file Ä‘áº¡t sá»‘ trang; chÆ°a khÃ³a tÃªn tÃ i liá»‡u demo trong code |
| Bá»™ tÃ i liá»‡u chuáº©n bá»‹ hackathon | `docs/` vÃ  `problem.txt` | ÄÃ£ cÃ³ kiáº¿n trÃºc, tech stack, API, káº¿ hoáº¡ch, test vÃ  task tá»«ng ngÆ°á»i |

## Äang lÃ m

| Háº¡ng má»¥c | Tráº¡ng thÃ¡i |
|---|---|
| Chuáº©n hÃ³a há»£p Ä‘á»“ng dá»¯ liá»‡u vÃ  API | ÄÃ£ thiáº¿t káº¿ trong tÃ i liá»‡u, chÆ°a triá»ƒn khai vÃ o code |
| Chuáº©n bá»‹ mÃ´i trÆ°á»ng cháº¡y chung | ChÆ°a xÃ¡c nháº­n Ä‘á»§ dependencies, model API key vÃ  cáº¥u hÃ¬nh frontend/backend |
| Kiá»ƒm tra dá»¯ liá»‡u demo | ÄÃ£ xÃ¡c nháº­n sá»‘ trang vÃ  text layer; chÆ°a táº¡o golden answers |

## ChÆ°a lÃ m

| Háº¡ng má»¥c | Äiá»u kiá»‡n hoÃ n thÃ nh |
|---|---|
| Nháº­p DOCX | Tráº£ cÃ¹ng schema vá»›i PDF vÃ  giá»¯ cáº¥u trÃºc Ä‘oáº¡n/tiÃªu Ä‘á» |
| Báº£ng áº£nh/scan | Chá»‰ phÃ¡t hiá»‡n/crop báº±ng YOLOv8; trang khÃ´ng cÃ³ text layer khÃ´ng Ä‘Æ°á»£c OCR |
| PhÃ¡t hiá»‡n báº£ng áº£nh/scan | YOLOv8 table-specific tráº£ bbox/confidence/class vÃ  crop; khÃ´ng cÃ³ OCR/cell/Markdown |
| TÃ³m táº¯t LLM cÃ³ cáº¥u trÃºc | Äá»§ 4 má»¥c báº¯t buá»™c, cÃ³ citation vÃ  schema validation |
| Giáº£i thÃ­ch thuáº­t ngá»¯ | Ãt nháº¥t 10 thuáº­t ngá»¯ Ä‘Ãºng ngá»¯ cáº£nh, cÃ³ nguá»“n |
| CÃ¢u há»i pháº£n biá»‡n | Ãt nháº¥t 5 cÃ¢u riÃªng theo tÃ i liá»‡u, cÃ³ lÃ½ do vÃ  nguá»“n |
| VÄƒn báº£n liÃªn quan | TrÃ­ch cÄƒn cá»© vÃ  Ä‘á»‘i chiáº¿u catalog tÃ i liá»‡u cÃ´ng khai |
| Q&A grounded | Retrieval theo ná»™i dung, tráº£ trang + má»¥c/Ä‘iá»u hoáº·c tá»« chá»‘i |
| FastAPI vÃ  job processing | Upload, status, report, question hoáº¡t Ä‘á»™ng theo API contract |
| TÃ­ch há»£p Next.js | Upload tháº­t, progress, report, viewer vÃ  chat |
| Benchmark 40+ trang | TÃ i liá»‡u táº¡i `DEMO_DOCUMENT_PATH` hoÃ n táº¥t dÆ°á»›i 60 giÃ¢y, cÃ³ log cáº¥u hÃ¬nh mÃ¡y |
| Kiá»ƒm thá»­ nghiá»‡m thu | Äáº¡t toÃ n bá»™ checklist trong `ACCEPTANCE_TESTS.md` |
| Deck cÃ³ sá»‘ liá»‡u tháº­t | Thay toÃ n bá»™ placeholder báº±ng benchmark vÃ  áº£nh demo |

## VÆ°á»›ng máº¯c hiá»‡n táº¡i

- ÄÃ£ xÃ¡c nháº­n checkpoint `models/table_detect_yolov8.pt` cÃ³ class `bordered` vÃ  `borderless`; runtime GPU pháº£i Ä‘Æ°á»£c kiá»ƒm tra báº±ng smoke test.
- ChÆ°a chá»‘t nhÃ  cung cáº¥p LLM, model, API key vÃ  háº¡n má»©c gá»i.
- ChÆ°a cÃ³ golden set Ä‘á»ƒ Ä‘o Ä‘á»™ Ä‘Ãºng cá»§a thuáº­t ngá»¯, cÃ¢u há»i vÃ  citation.
