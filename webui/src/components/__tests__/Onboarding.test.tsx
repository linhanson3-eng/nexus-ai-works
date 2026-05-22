import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Onboarding } from "../Onboarding";

vi.mock("../../lib/api", () => ({
  fetchCsrfToken: vi.fn(),
}));

function renderOnboarding(onDone = vi.fn()) {
  return render(
    <MemoryRouter>
      <Onboarding onDone={onDone} />
    </MemoryRouter>,
  );
}

describe("Onboarding", () => {
  it("renders first step title", () => {
    renderOnboarding();
    expect(screen.getByText("欢迎使用 Nexus AI Works")).toBeDefined();
  });

  it("shows step indicators", () => {
    renderOnboarding();
    const indicators = document.querySelectorAll(".rounded-full");
    // 4 step indicators
    expect(indicators.length).toBeGreaterThanOrEqual(4);
  });

  it("advances to next step on action click", async () => {
    renderOnboarding();
    const nextBtn = screen.getByText(/开始配置/);
    await userEvent.click(nextBtn);
    expect(await screen.findByText(/配置 LLM 提供商/)).toBeDefined();
  });

  it("calls onDone when skip is clicked", async () => {
    const onDone = vi.fn();
    renderOnboarding(onDone);
    const skipBtn = screen.getByText("跳过引导");
    await userEvent.click(skipBtn);
    expect(onDone).toHaveBeenCalledOnce();
  });

  it("calls onDone on last step completion", async () => {
    const onDone = vi.fn();
    renderOnboarding(onDone);

    // Click through all steps
    for (let i = 0; i < 3; i++) {
      await userEvent.click(screen.getByRole("button", { name: /开始|前往|配置/ }));
    }
    // Last step
    const lastBtn = screen.getByRole("button", { name: /开始使用/ });
    await userEvent.click(lastBtn);
    expect(onDone).toHaveBeenCalled();
  });
});
