# BÃ n giao HAU â€” Intelligence vÃ  YOLOv8 table detection

## Context

Lá»›p intelligence Ä‘Æ°á»£c tÃ¡ch khá»i ingestion vÃ  model client Ä‘á»ƒ cÃ¡c consumer cÃ³
thá»ƒ dÃ¹ng fixture/test double trÆ°á»›c khi tÃ­ch há»£p production. Theo quyáº¿t Ä‘á»‹nh ká»¹
thuáº­t má»›i, toÃ n bá»™ PaddleOCR/PP-Structure Ä‘Ã£ Ä‘Æ°á»£c loáº¡i bá»; pipeline chá»‰ dÃ¹ng
YOLOv8 hiá»‡n cÃ³ Ä‘á»ƒ phÃ¡t hiá»‡n vÃ  cáº¯t vÃ¹ng báº£ng.

## Contract intelligence

```python
from backend.intelligence import IntelligenceReport, NormalizedDocument, build_intelligence

report = await build_intelligence(
    NormalizedDocument.model_validate(payload),
    call_llm=shared_call_llm,
    citation_validator=validate_citations,
)
```

- `call_llm(messages, response_model)` pháº£i lÃ  client dÃ¹ng chung vÃ  tráº£ object
  tÆ°Æ¡ng thÃ­ch `response_model`.
- Map cháº¡y theo batch 7 trang máº·c Ä‘á»‹nh; cáº¥u hÃ¬nh chá»‰ cho phÃ©p 6â€“8 trang.
- Output thiáº¿u nguá»“n bá»‹ loáº¡i. Citation há»£p lá»‡ pháº£i lÃ  `chunk_id` thuá»™c document;
  validator ngoÃ i chá»‰ cÃ³ thá»ƒ thu háº¹p whitelist, khÃ´ng thá»ƒ má»Ÿ rá»™ng.
- `IntelligenceReport.model_json_schema()` lÃ  JSON schema cho structured output.
- `stage_timings` ghi map/reduce/validation; `quality` ghi checklist Ä‘á»‹nh lÆ°á»£ng.

Fixture dÃ¹ng chung:

- `docs/fixtures/normalized_document.mock.json`
- `docs/fixtures/intelligence_report.mock.json`

## Contract YOLOv8

```python
from backend.pipeline import TableDetector

detector = TableDetector(
    "models/table_detect_yolov8.pt",
    confidence_threshold=0.25,
    device=0,
)
detections = detector.detect(page_image)
crops = detector.crop_tables(page_image, [item.bbox for item in detections])
```

Model Ä‘Ã£ xÃ¡c nháº­n lÃ  checkpoint table-specific vá»›i hai lá»›p `bordered` vÃ 
`borderless`. Model path lÃ  báº¯t buá»™c; thiáº¿u checkpoint sáº½ fail-closed thay vÃ¬
tá»± táº£i weight COCO chung.

| TrÆ°á»ng | CÃ³ tá»« YOLOv8 | Ã nghÄ©a |
|---|---:|---|
| `bbox` | CÃ³ | VÃ¹ng báº£ng trong há»‡ tá»a Ä‘á»™ áº£nh |
| `confidence` | CÃ³ | Äá»™ tin cáº­y detection |
| `class_id` | CÃ³ | `bordered` hoáº·c `borderless` |
| crop áº£nh | CÃ³ | áº¢nh con phá»¥c vá»¥ consumer tiáº¿p theo |
| text tiáº¿ng Viá»‡t | KhÃ´ng | YOLO khÃ´ng nháº­n dáº¡ng kÃ½ tá»± |
| row/column/cell | KhÃ´ng | YOLO khÃ´ng nháº­n dáº¡ng cáº¥u trÃºc báº£ng |
| Markdown/JSON ná»™i dung | KhÃ´ng | KhÃ´ng Ä‘Æ°á»£c táº¡o placeholder hoáº·c suy diá»…n |

`PdfProcessingPipeline` giá»¯ nguyÃªn native PDF text vÃ  chá»‰ Ä‘Ã­nh kÃ¨m detection
metadata. Pipeline khÃ´ng che vÃ¹ng báº£ng rá»“i thay báº±ng ná»™i dung rá»—ng, nhá» Ä‘Ã³ trÃ¡nh
máº¥t text layer khi khÃ´ng cÃ³ OCR thay tháº¿.

## Reliability constraints

- KhÃ´ng cÃ³ model table-specific thÃ¬ dá»«ng vá»›i `YoloModelConfigurationError`.
- Bounding box Ä‘Æ°á»£c clip vÃ o kÃ­ch thÆ°á»›c áº£nh; vÃ¹ng rá»—ng bá»‹ loáº¡i.
- KhÃ´ng cÃ²n export `ocr_page`, `ocr_table`, `PaddleOcrAdapter` hay
  `table_to_markdown` placeholder.
- Map batch lá»—i má»™t pháº§n váº«n reduce cÃ¡c batch há»£p lá»‡; táº¥t cáº£ batch lá»—i gÃ¢y
  `IntelligenceGenerationError`.
- KhÃ´ng cÃ³ chunk thÃ¬ tráº£ report rá»—ng vÃ  khÃ´ng gá»i model.

## Giá»›i háº¡n nghiá»‡m thu HAU-05

HAU-05 theo mÃ´ táº£ gá»‘c yÃªu cáº§u OCR tiáº¿ng Viá»‡t, Ä‘Ãºng hÃ ng/cá»™t vÃ  Markdown/JSON.
YOLOv8 thuáº§n khÃ´ng thá»ƒ Ä‘Ã¡p á»©ng cÃ¡c Ä‘áº§u ra nÃ y. Pháº§n Ä‘áº¡t Ä‘Æ°á»£c sau thay Ä‘á»•i pháº¡m vi
lÃ  detection/crop trÃªn áº£nh tháº­t vá»›i `page`, `bbox`, `confidence` vÃ  class; pháº§n
OCR ná»™i dung Ä‘Æ°á»£c Ä‘Ã¡nh dáº¥u khÃ´ng Ä‘áº¡t thay vÃ¬ táº¡o dá»¯ liá»‡u giáº£.
