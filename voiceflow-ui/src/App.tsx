import { useState, useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { VoiceOverlay, type VoiceState } from "./components/VoiceOverlay";

interface StateEvent {
  state: VoiceState;
  mode?: string;
}

interface ResultEvent {
  type: string;
  text: string;
  shortcut: string | null;
}

const isDev = import.meta.env.DEV;

export default function App() {
  const [state, setState] = useState<VoiceState>("hidden");
  const [mode, setMode] = useState<string | null>(null);
  const [lastText, setLastText] = useState<string>("");

  useEffect(() => {
    const unlistenState = listen<StateEvent>("voiceflow://state", (event) => {
      const { state: newState, mode: newMode } = event.payload;
      setState(newState);
      if (newMode) setMode(newMode);

      if (newState === "hidden") {
        if (newMode) setMode(null);
      }
    });

    const unlistenResult = listen<ResultEvent>("voiceflow://result", (event) => {
      setLastText(event.payload.text || "");
    });

    return () => {
      unlistenState.then((fn) => fn());
      unlistenResult.then((fn) => fn());
    };
  }, []);

  return (
    <div
      className="flex flex-col items-center justify-center w-full h-full"
      style={{ background: "transparent" }}
    >
      <VoiceOverlay state={state} />

      {isDev && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 flex gap-1 bg-gray-800/80 px-2 py-1 rounded-lg text-[10px] text-gray-400">
          <span>{state}</span>
          {mode && <span className="text-indigo-400">({mode})</span>}
          {lastText && <span className="text-green-400 ml-2">&quot;{lastText.slice(0, 20)}&quot;</span>}
        </div>
      )}
    </div>
  );
}
