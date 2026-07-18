import {
  AlertTriangle,
  BookOpenCheck,
  CheckCircle2,
  Clock3,
  FileSearch,
  FileText,
  HelpCircle,
  MessageSquareText,
  UploadCloud,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const stats = [
  { label: "Tài liệu test", value: "01.pdf", detail: "4 trang", icon: FileText },
  { label: "Thời gian xử lý", value: "1.01s", detail: "MVP smoke test", icon: Clock3 },
  { label: "Bảng phát hiện", value: "2", detail: "YOLOv8 table detector", icon: FileSearch },
  { label: "Nội dung trích xuất", value: "5,762", detail: "ký tự đã stitch", icon: BookOpenCheck },
];

const summary = [
  {
    title: "Bối cảnh",
    items: [
      "Tài liệu mô tả cấu trúc định dạng đề thi và các phần kiến thức cần nắm trước buổi làm việc.",
      "Nội dung có nhiều thuật ngữ về tự luận, trắc nghiệm, triết học, kinh tế học vĩ mô và lý luận nhà nước pháp luật.",
    ],
  },
  {
    title: "Nội dung chính",
    items: [
      "Đề thi gồm phần tự luận bắt buộc và phần trắc nghiệm tự chọn.",
      "Tổng điểm 100, trong đó tự luận 30 điểm và trắc nghiệm 70 điểm.",
      "Thời gian làm bài 150 phút, hình thức làm bài trên máy.",
    ],
  },
  {
    title: "Điểm cần quyết định",
    items: [
      "Thống nhất phạm vi các lĩnh vực kiến thức được lựa chọn.",
      "Làm rõ cách áp dụng tỷ trọng đánh giá: 20% biết, 30% hiểu, 50% vận dụng.",
    ],
  },
  {
    title: "Tác động",
    items: [
      "Người dự họp cần chuẩn bị nội dung theo từng nhóm kiến thức và năng lực đánh giá.",
      "Các tiêu chí đánh giá ảnh hưởng trực tiếp tới cách ôn tập, ra đề và tổ chức thi.",
    ],
  },
  {
    title: "Rủi ro / lưu ý",
    items: [
      "Cần tránh hiểu sai giữa nội dung bắt buộc và nội dung tự chọn.",
      "Cần kiểm tra lại bảng biểu gốc khi dùng kết quả markdown vì table parser hiện là placeholder.",
    ],
  },
];

const terms = [
  ["Nghị quyết", "Văn bản thể hiện quyết định hoặc chủ trương được cơ quan có thẩm quyền thông qua.", "Trang 4"],
  ["Trách nhiệm", "Nghĩa vụ được giao cho cơ quan, tổ chức hoặc cá nhân thực hiện.", "Trang 2, 3"],
  ["Tự luận", "Dạng câu hỏi yêu cầu trình bày lập luận, phân tích và quan điểm bằng văn viết.", "Trang 1, 2"],
  ["Trắc nghiệm", "Dạng câu hỏi có lựa chọn trả lời, dùng để kiểm tra phạm vi kiến thức rộng.", "Trang 1, 2"],
  ["Nghị luận xã hội", "Bài phân tích, bàn luận về vấn đề xã hội, chính trị, kinh tế hoặc văn hóa.", "Trang 1"],
  ["Kinh tế học vĩ mô", "Lĩnh vực nghiên cứu các biến số lớn của nền kinh tế.", "Trang 2, 3"],
  ["Triết học", "Lĩnh vực nghiên cứu thế giới quan, phương pháp luận và nhận thức.", "Trang 1, 2, 3"],
  ["Lý luận nhà nước và pháp luật", "Môn học về bản chất, tổ chức nhà nước và hệ thống pháp luật.", "Trang 1, 3"],
  ["Tỷ trọng đánh giá", "Tỷ lệ phân bổ tiêu chí được dùng để chấm điểm, đánh giá.", "Trang 1"],
  ["Vận dụng", "Mức độ yêu cầu áp dụng kiến thức để xử lý tình huống.", "Trang 1"],
];

const questions = [
  "Nội dung nào là bắt buộc phải quyết định hoặc thống nhất trong cuộc họp?",
  "Các tiêu chí, tỷ trọng hoặc căn cứ đánh giá đã đủ rõ để triển khai chưa?",
  "Những nhóm đối tượng hoặc đơn vị nào chịu tác động trực tiếp từ nội dung này?",
  "Có điểm nào cần bổ sung căn cứ pháp lý, dữ liệu hoặc tài liệu liên quan không?",
  "Rủi ro lớn nhất nếu triển khai theo nội dung hiện tại là gì và ai chịu trách nhiệm xử lý?",
];

export default function Home() {
  return (
    <main className="min-h-screen bg-background">
      <section className="mx-auto max-w-7xl px-6 pt-32 pb-10">
        <div className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
          <div className="space-y-7">
            <Badge variant="outline" className="h-7 rounded-full px-3">
              Paperless Meetings MVP
            </Badge>
            <div className="space-y-5">
              <h1 className="max-w-4xl text-4xl font-semibold tracking-tight text-foreground sm:text-6xl">
                Dashboard đọc nhanh tài liệu họp cấp tỉnh
              </h1>
              <p className="max-w-2xl text-lg leading-8 text-muted-foreground">
                Upload PDF/Word, hệ thống trích xuất nội dung, tóm tắt theo điểm
                quyết định, giải thích thuật ngữ và trả lời câu hỏi tiếng Việt
                với trích dẫn trang.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button size="lg" className="rounded-full">
                <UploadCloud className="size-4" />
                Upload tài liệu
              </Button>
              <Button size="lg" variant="outline" className="rounded-full">
                Xem kết quả demo 01.pdf
              </Button>
            </div>
          </div>

          <Card className="border-foreground/10 bg-gradient-to-br from-card to-muted/40 shadow-2xl shadow-foreground/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle2 className="size-5 text-emerald-500" />
                Kết quả xử lý gần nhất
              </CardTitle>
              <CardDescription>
                Smoke test chạy từ pipeline Python với YOLOv8 table detection.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              {stats.map((item) => (
                <div key={item.label} className="rounded-xl border bg-background/70 p-4">
                  <item.icon className="mb-3 size-5 text-muted-foreground" />
                  <div className="text-2xl font-semibold">{item.value}</div>
                  <div className="text-sm font-medium">{item.label}</div>
                  <div className="text-xs text-muted-foreground">{item.detail}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </section>

      <section id="dashboard" className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[280px_1fr]">
        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Luồng xử lý</CardTitle>
              <CardDescription>Dưới 60 giây cho tài liệu dài.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {["PDF native", "YOLO detect bảng", "Mask text vùng bảng", "Stitch text + markdown", "Summary / Q&A"].map((step, index) => (
                <div key={step} className="flex items-center gap-3 rounded-lg border p-3">
                  <span className="flex size-7 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">
                    {index + 1}
                  </span>
                  <span className="text-sm">{step}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Trạng thái MVP</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Status label="Extraction pipeline" done />
              <Status label="Dashboard template" done />
              <Status label="Table markdown AI" />
              <Status label="LLM production" />
            </CardContent>
          </Card>
        </aside>

        <div className="space-y-6">
          <Card id="summary">
            <CardHeader>
              <CardTitle>Tóm tắt có cấu trúc</CardTitle>
              <CardDescription>
                Phù hợp yêu cầu: bối cảnh, nội dung chính, điểm quyết định và tác động.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              {summary.map((section) => (
                <div key={section.title} className="rounded-xl border p-4">
                  <h3 className="mb-3 font-semibold">{section.title}</h3>
                  <ul className="space-y-2 text-sm text-muted-foreground">
                    {section.items.map((item) => (
                      <li key={item} className="leading-6">- {item}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
            <Card id="terms">
              <CardHeader>
                <CardTitle>Thuật ngữ được highlight</CardTitle>
                <CardDescription>10 thuật ngữ chuyên ngành kèm giải thích và trang xuất hiện.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {terms.map(([term, explanation, pages]) => (
                  <div key={term} className="rounded-xl border p-4">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <Badge>{term}</Badge>
                      <Badge variant="outline">{pages}</Badge>
                    </div>
                    <p className="text-sm leading-6 text-muted-foreground">{explanation}</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card id="questions">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <HelpCircle className="size-5" />
                    Câu hỏi gợi ý
                  </CardTitle>
                  <CardDescription>Gợi ý cho lãnh đạo chuẩn bị phản biện.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {questions.map((question, index) => (
                    <div key={question} className="rounded-xl border p-3 text-sm leading-6">
                      <span className="mr-2 font-semibold">{index + 1}.</span>
                      {question}
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card id="qa">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <MessageSquareText className="size-5" />
                    Hỏi đáp có citation
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="rounded-xl border bg-muted/40 p-4">
                    <p className="text-sm font-medium">Người dùng hỏi</p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Tài liệu này yêu cầu người dự họp cần lưu ý những nội dung chính nào?
                    </p>
                  </div>
                  <div className="rounded-xl border p-4">
                    <p className="text-sm font-medium">AI trả lời</p>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      Cần lưu ý cơ cấu điểm, thời gian làm bài, hình thức làm bài trên máy,
                      tỷ trọng đánh giá và các nhóm kiến thức tự chọn.
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {["Trang 1", "Trang 2", "Trang 3"].map((page) => (
                        <Badge key={page} variant="outline">{page}</Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          <Card id="roadmap">
            <CardHeader>
              <CardTitle>Roadmap triển khai tại UBND</CardTitle>
              <CardDescription>Từ demo local tới triển khai an toàn trong cơ quan.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              {[
                ["MVP", "Local dashboard, PDF extraction, summary, terms, questions, Q&A."],
                ["Pilot", "Kết nối LLM tiếng Việt, vector search, Word upload, kiểm duyệt thuật ngữ."],
                ["Production", "SSO, audit log, cache tài liệu họp, phân quyền và triển khai nội bộ."],
              ].map(([title, description]) => (
                <div key={title} className="rounded-xl border p-4">
                  <h3 className="mb-2 font-semibold">{title}</h3>
                  <p className="text-sm leading-6 text-muted-foreground">{description}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-900 dark:text-amber-200">
            <AlertTriangle className="mt-0.5 size-5 shrink-0" />
            <p>
              Demo hiện dùng dữ liệu tĩnh từ test `01.pdf`. Bước sau cần nối API Python để upload file thật và stream kết quả xử lý vào dashboard.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}

function Status({ label, done = false }: { label: string; done?: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-lg border p-3">
      <span>{label}</span>
      <Badge variant={done ? "default" : "outline"}>{done ? "Done" : "Next"}</Badge>
    </div>
  );
}
