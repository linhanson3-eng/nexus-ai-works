import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Dashboard } from "../Dashboard";

vi.mock("../../lib/api", () => ({
  api: {
    orgStatus: vi.fn().mockResolvedValue({
      departments: [],
      total_agents: 0,
      warehouse: "/tmp/warehouse",
      warehouse_products: {},
    }),
    listWorkshops: vi.fn().mockResolvedValue([]),
    listWorkflows: vi.fn().mockResolvedValue([]),
    listBoards: vi.fn().mockResolvedValue([]),
  },
  fetchCsrfToken: vi.fn(),
}));

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  );
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders dashboard heading", async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("总览")).toBeDefined();
    });
  });

  it("shows system status online", async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("在线")).toBeDefined();
    });
  });

  it("shows workspace count", async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("项目")).toBeDefined();
    });
  });

  it("shows empty state when no workshops", async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("暂无项目")).toBeDefined();
    });
  });
});
