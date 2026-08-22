import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Login } from "@/pages/Login";

function withRouter(ui: React.ReactElement) {
  return <MemoryRouter>{ui}</MemoryRouter>;
}

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

describe("Login", () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("renders the form with demo persona shortcuts", () => {
    render(withRouter(<Login />));
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByText(/priya sharma/i)).toBeInTheDocument();
  });

  it("shows a clear error on invalid credentials (401)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Invalid email or password" } }), {
          status: 401,
        }),
      ),
    );
    render(withRouter(<Login />));
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid email or password/i);
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("stores the session and navigates on success", async () => {
    const session = {
      access_token: "tok",
      refresh_token: "ref",
      user: { id: "u1", email: "e@x", full_name: "E", role: "EXECUTIVE", job_title: "", region_scope: [], organization: "Apex Foods", organization_id: "o1" },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ data: session, meta: { request_id: "r", timestamp: "t" } }), { status: 200 }),
      ),
    );
    render(withRouter(<Login />));
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/scenarios"));
    expect(localStorage.getItem("rf.session")).toContain("tok");
  });
});
