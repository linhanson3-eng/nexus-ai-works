import { Layout } from "./components/Layout";
import { Dashboard } from "./components/Dashboard";
import { WorkshopList } from "./components/WorkshopList";
import { KanbanBoard } from "./components/KanbanBoard";
import { WorkflowList } from "./components/WorkflowList";

function App() {
  const path = window.location.pathname;
  const active = path === "/" ? "/" : "/" + (path.split("/")[1] || "");

  const page = (() => {
    if (path === "/") return <Dashboard />;
    if (path.startsWith("/workshops")) return <WorkshopList />;
    if (path.startsWith("/kanban")) return <KanbanBoard />;
    if (path.startsWith("/workflows")) return <WorkflowList />;
    return <Dashboard />;
  })();

  return <Layout active={active}>{page}</Layout>;
}

export default App;
