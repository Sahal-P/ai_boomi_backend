"use client";
import { AssistantScreen } from "@/components/assistant/assistant-screen";
import { useAssistant } from "@/hooks/use-assistant";
export default function AssistantPage() {
  const s = useAssistant();
  return (
    <AssistantScreen
      question={s.question}
      onQuestion={s.setQuestion}
      style={s.style}
      onStyle={s.setStyle}
      answer={s.answer}
      error={s.error}
      busy={s.busy}
      transcribing={s.transcribing}
      speaking={s.speaking}
      audioUrl={s.audioUrl}
      notice={s.notice}
      voiceError={s.voiceError}
      recording={s.recording.recording}
      requestingMic={s.recording.requesting}
      recorderError={s.recording.error}
      onRecord={() => void s.recording.start()}
      onStop={s.recording.stop}
      onAsk={() => void s.ask()}
      onListen={() => void s.listen()}
    />
  );
}
