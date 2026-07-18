import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ReportResponse } from "../lib/antipaper-api";
import { CitationButtonList } from "./Workspace";

const report = {
  citations: {
    one: { page: 1, chapter: null, article: null, clause: null, excerpt: "Nguồn một" },
    two: { page: 2, chapter: null, article: null, clause: null, excerpt: "Nguồn hai" },
    three: { page: 3, chapter: null, article: null, clause: null, excerpt: "Nguồn ba" },
    four: { page: 4, chapter: null, article: null, clause: null, excerpt: "Nguồn bốn" },
  },
} as unknown as ReportResponse;

describe("CitationButtonList", () => {
  it("shows all valid citations through three buttons and removes unknown or duplicate IDs", () => {
    render(<CitationButtonList ids={["one", "two", "two", "unknown", "three"]} report={report} onSelectCitation={vi.fn()} />);

    expect(screen.getByRole("button", { name: /trang 1/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /trang 2/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /trang 3/i })).toBeInTheDocument();
    expect(screen.queryByText("(Xem thêm)")).not.toBeInTheDocument();
  });

  it("collapses a fourth citation until the user selects xem thêm", () => {
    const onSelectCitation = vi.fn();
    render(<CitationButtonList ids={["one", "two", "three", "four"]} report={report} onSelectCitation={onSelectCitation} />);

    expect(screen.queryByRole("button", { name: /trang 4/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "(Xem thêm)" }));
    fireEvent.click(screen.getByRole("button", { name: /trang 4/i }));

    expect(screen.getByRole("button", { name: "(Thu gọn)" })).toBeInTheDocument();
    expect(onSelectCitation).toHaveBeenCalledWith("four");
  });
});
