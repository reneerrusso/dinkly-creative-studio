import { AgentOperationsSettings } from "@/components/agent-operations-settings";
import { DinklyAgentSettings } from "@/components/dinkly-agent-settings";
import { ImageGenerationSettingsPanel } from "@/components/image-generation-settings";
import { PageHeader } from "@/components/page-header";
import { SlackSettings } from "@/components/slack-settings";

export default function SettingsPage() {
  return <div className="mx-auto max-w-6xl space-y-12 pb-16"><PageHeader eyebrow="DINKLY Agent" title="Settings" description="Keep the employee online, connect its providers and channels, and set hard cost limits. Creative work stays in the Agent desk and Brain."/><AgentOperationsSettings/><ImageGenerationSettingsPanel/><SlackSettings/><DinklyAgentSettings/></div>;
}
