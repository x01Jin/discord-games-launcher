import { CataloguePage } from "./modules/catalogue";
import { LibraryPage } from "./modules/library";
import { QuestsPage } from "./modules/quests";
import { SettingsPage } from "./modules/settings";
import { Sidebar, Toasts } from "./shared/components";
import { useDcglEvents } from "./shared/hooks";
import { useUiStore } from "./shared/store/ui-store";

function App() {
  const page = useUiStore((state) => state.page);
  useDcglEvents();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-canvas text-ink">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {page === "quests" ? (
          <QuestsPage />
        ) : page === "catalogue" ? (
          <CataloguePage />
        ) : page === "library" ? (
          <LibraryPage />
        ) : (
          <SettingsPage />
        )}
      </main>
      <Toasts />
    </div>
  );
}

export default App;
