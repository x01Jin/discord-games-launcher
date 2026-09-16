import { CataloguePage } from "./modules/catalogue";
import { LibraryPage } from "./modules/library";
import { Footer, Header, StatsModal, Tabs, Toasts } from "./shared/components";
import { useDcglEvents } from "./shared/hooks";
import { useUiStore } from "./shared/store/ui-store";

function App() {
  const tab = useUiStore((s) => s.tab);
  useDcglEvents();

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-ink text-white">
      <div className="z-30 shrink-0 border-b border-white/5 bg-ink">
        <Header />
        <Tabs />
      </div>
      <main className="min-h-0 flex-1 overflow-hidden px-6">
        {tab === "catalogue" ? <CataloguePage /> : <LibraryPage />}
      </main>
      <Footer />
      <StatsModal />
      <Toasts />
    </div>
  );
}

export default App;
