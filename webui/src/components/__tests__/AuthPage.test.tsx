import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthPage } from "../AuthPage";
import { AuthProvider } from "../../lib/AuthContext";

vi.mock("../../lib/api", () => ({
  api: {
    marketLogin: vi.fn(),
    marketRegister: vi.fn(),
  },
  fetchCsrfToken: vi.fn(),
}));

function renderAuthPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <AuthPage />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("AuthPage", () => {
  it("renders login form by default", async () => {
    renderAuthPage();
    const loginBtn = await screen.findAllByText("登录");
    expect(loginBtn.length).toBeGreaterThan(0);
  });

  it("shows username and password inputs", async () => {
    renderAuthPage();
    expect(screen.getByPlaceholderText("输入用户名")).toBeDefined();
    expect(screen.getByPlaceholderText("输入密码")).toBeDefined();
  });

  it("has register link", async () => {
    renderAuthPage();
    expect(screen.getByText("立即注册")).toBeDefined();
  });

  it("switches to register mode", async () => {
    renderAuthPage();
    const registerTab = screen.getByRole("button", { name: "注册" });
    await userEvent.click(registerTab);
    // After switching, the form submit button should also say 注册
    const submitBtn = screen.getByRole("button", { name: /注册/ });
    expect(submitBtn).toBeDefined();
  });
});
