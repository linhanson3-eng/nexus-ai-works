import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ToastProvider, useToast } from "../Toast";

function TestConsumer({ onToast }: { onToast: (t: ReturnType<typeof useToast>) => void }) {
  const toast = useToast();
  onToast(toast);
  return <div data-testid="consumer" />;
}

describe("ToastProvider", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders children", () => {
    render(
      <ToastProvider>
        <div data-testid="child">Hello</div>
      </ToastProvider>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("throws when useToast is used outside provider", () => {
    const Consumer = () => {
      try {
        useToast();
        return <div>ok</div>;
      } catch {
        return <div>error</div>;
      }
    };

    const { container } = render(<Consumer />);
    expect(container.textContent).toBe("error");
  });

  it("shows success toast", async () => {
    let capturedToast: ReturnType<typeof useToast> | null = null;

    render(
      <ToastProvider>
        <TestConsumer onToast={t => { capturedToast = t; }} />
      </ToastProvider>,
    );

    act(() => {
      capturedToast!.success("操作成功");
    });

    expect(screen.getByText("操作成功")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3500);
    });

    expect(screen.queryByText("操作成功")).not.toBeInTheDocument();
  });

  it("shows error toast", () => {
    let capturedToast: ReturnType<typeof useToast> | null = null;

    render(
      <ToastProvider>
        <TestConsumer onToast={t => { capturedToast = t; }} />
      </ToastProvider>,
    );

    act(() => {
      capturedToast!.error("操作失败");
    });

    expect(screen.getByText("操作失败")).toBeInTheDocument();
  });

  it("shows info toast", () => {
    let capturedToast: ReturnType<typeof useToast> | null = null;

    render(
      <ToastProvider>
        <TestConsumer onToast={t => { capturedToast = t; }} />
      </ToastProvider>,
    );

    act(() => {
      capturedToast!.info("提示信息");
    });

    expect(screen.getByText("提示信息")).toBeInTheDocument();
  });
});
