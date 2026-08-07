import type { LucideIcon } from "lucide-react";
import { AlertTriangle, BookHeart, BookOpenText, BrainCircuit, Download, FileCheck2, FileText, Settings, Sparkles } from "lucide-react";

export interface AgentAction {
  label: string;
  href: string;
  primary?: boolean;
}

export interface AgentDefinition {
  id: string;
  displayName: string;
  role: string;
  personality: string;
  avatarPath: string;
  route: string;
  statusColor: string;
  accentSoft: string;
  objective: string;
  note: string;
  watchlist: string[];
  suggestions: string[];
  actions: AgentAction[];
  owns: string[];
}

export const AGENT_ASSET_VERSION = "3";

export const canonicalAgentIds = [
  "creative-director",
  "concept-generator",
  "prompt-agent",
  "social-intelligence",
  "art-review",
  "brand-integration",
  "motion-director",
] as const;

export type CanonicalAgentId = (typeof canonicalAgentIds)[number];

export const agents: AgentDefinition[] = [
  {
    id: "creative-director",
    displayName: "Creative Director",
    role: "Creative direction and brand strategy",
    personality: "Obsessed with making people feel something.",
    avatarPath: "/agents/creative-director.png",
    route: "/agents/creative-director",
    statusColor: "#93643f",
    accentSoft: "#f4e5d2",
    objective: "Find the smallest ordinary moment with the clearest emotional truth.",
    note: "People are responding to ordinary moments becoming meaningful. Keep the activity simple and let togetherness do the emotional work.",
    watchlist: ["Emotional clarity", "Story quality", "Fresh everyday moments"],
    suggestions: ["Develop an overlooked routine", "Review the weakest story score", "Revisit a proven theme from a new angle"],
    actions: [
      { label: "Generate concepts", href: "/concepts/new", primary: true },
      { label: "Review stories", href: "/concepts" },
      { label: "Open Story Library", href: "/story-library" },
    ],
    owns: ["/agents/creative-director", "/"],
  },
  {
    id: "concept-generator",
    displayName: "Concept Generator",
    role: "Daily storyline development",
    personality: "Turns what people are feeling right now into DINKLY stories.",
    avatarPath: "/agents/concept-generator.png",
    route: "/agents/concept-generator",
    statusColor: "#8b5d36",
    accentSoft: "#efe2cf",
    objective: "Place thirty original, evidence-informed DINKLY ideas on the daily creative desk.",
    note: "I protect originality first, then refine the strongest ordinary moments into a queue that is ready to make.",
    watchlist: ["Fresh daily ideas", "Preference memory", "Used-storyline protection"],
    suggestions: ["Generate today’s concepts", "Review the Production Queue", "Tell me what to make more or less of"],
    actions: [
      { label: "Open today’s concepts", href: "/agents/concept-generator", primary: true },
      { label: "Production Queue", href: "/agents/concept-generator?view=queue" },
      { label: "Content preferences", href: "/agents/concept-generator?view=preferences" },
    ],
    owns: ["/agents/concept-generator", "/concepts"],
  },
  {
    id: "prompt-agent",
    displayName: "Prompt Agent",
    role: "Nano Banana prompt production",
    personality: "Never writes the same prompt twice.",
    avatarPath: "/agents/prompt-agent.png",
    route: "/agents/prompt-agent",
    statusColor: "#d66c32",
    accentSoft: "#f9dfd0",
    objective: "Turn the approved scene into one concise, production-ready Nano Banana brief.",
    note: "Character accuracy comes first. Every instruction should earn its place in the prompt.",
    watchlist: ["Nano Banana clarity", "Scene-specific safeguards", "Prompt history"],
    suggestions: ["Build from an approved concept", "Improve a prompt without bloating it", "Translate a reference scene into the DINKLY universe"],
    actions: [
      { label: "Generate prompt", href: "/prompt-builder", primary: true },
      { label: "Improve prompt", href: "/prompt-builder?mode=new" },
      { label: "Review prompt", href: "/projects/approved-comics" },
      { label: "Open Prompt History", href: "/projects/exports?view=prompts" },
    ],
    owns: ["/agents/prompt-agent", "/agents/prompt-engineer", "/prompt-builder"],
  },
  {
    id: "art-review",
    displayName: "Art Review",
    role: "Artwork quality control",
    personality: "Protects Dinko and Dinka at all costs.",
    avatarPath: "/agents/art-review.png",
    route: "/agents/art-review",
    statusColor: "#55775b",
    accentSoft: "#e1ecdc",
    objective: "Catch the highest-priority off-model detail before artwork moves forward.",
    note: "A precise correction protects more of a good image than a broad regeneration ever will.",
    watchlist: ["Character identity", "Anatomy", "Background and prop scale"],
    suggestions: ["Review the latest generation", "Inspect a sprite loop", "Open known failure patterns"],
    actions: [
      { label: "Review artwork", href: "/art-review", primary: true },
      { label: "Review sprite", href: "/art-review?mode=sprite" },
      { label: "Open Failure Library", href: "/failures" },
    ],
    owns: ["/agents/art-review", "/agents/art-reviewer", "/art-review"],
  },
  {
    id: "social-intelligence",
    displayName: "Social Intelligence",
    role: "Social evidence and trend intelligence",
    personality: "Studies what people share, what is rising, and what DINKLY should test next.",
    avatarPath: "/agents/social-intelligence.png",
    route: "/agents/social-intelligence",
    statusColor: "#61718b",
    accentSoft: "#e3e5f3",
    objective: "Compare owned and public post performance without confusing evidence, observation, and hypothesis.",
    note: "A standout matters only against the account’s baseline. Public signals can guide an original DINKLY test, but never prove causation or justify copying.",
    watchlist: ["Owned-account learning", "Public account baselines", "Budget-safe refreshes"],
    suggestions: ["Add monitored handles", "Analyze existing public data", "Turn a supported pattern into an original DINKLY direction"],
    actions: [
      { label: "Open Social Intelligence", href: "/agents/social-intelligence", primary: true },
      { label: "Owned-account learning", href: "/social-learning" },
      { label: "Provider settings", href: "/settings#social-data-providers" },
    ],
    owns: ["/agents/social-intelligence", "/social-learning"],
  },
  {
    id: "brand-integration",
    displayName: "Brand Integration",
    role: "Natural brand storytelling",
    personality: "Turns products into stories.",
    avatarPath: "/agents/brand-integration.png",
    route: "/agents/brand-integration",
    statusColor: "#aa761e",
    accentSoft: "#f9e9b8",
    objective: "Find the product that naturally belongs in the moment instead of interrupting it.",
    note: "The strongest placement replaces a prop the story already needs. It never asks the characters to become an advertisement.",
    watchlist: ["Natural product roles", "Evergreen versions", "Character-first accuracy"],
    suggestions: ["Find a brand fit for a concept", "Plan a placeholder-first workflow", "Create an evergreen campaign version"],
    actions: [
      { label: "Plan integration", href: "/brand-integrations", primary: true },
      { label: "Review brand-ready concepts", href: "/concepts" },
      { label: "Open integration rules", href: "/knowledge?doc=brand-integrations" },
    ],
    owns: ["/agents/brand-integration", "/agents/brand-partnerships", "/brand-integrations"],
  },
  {
    id: "motion-director",
    displayName: "Motion Director",
    role: "Animation and motion direction",
    personality: "Brings tiny moments to life.",
    avatarPath: "/agents/motion-director.png",
    route: "/agents/motion-director",
    statusColor: "#586575",
    accentSoft: "#dce9f3",
    objective: "Choose the smallest movement that makes the scene feel alive without deforming the characters.",
    note: "A blink, a breath, or one drifting heart is often enough. Motion should add feeling, not noise.",
    watchlist: ["Blink", "Idle", "Coffee sip", "Shared hug"],
    suggestions: ["Plan motion for an approved comic", "Build a subtle sprite loop", "Compose a shared character action"],
    actions: [
      { label: "Open Motion Studio", href: "/motion-studio", primary: true },
      { label: "Open Sprite Studio", href: "/sprite-studio" },
      { label: "Generate motion", href: "/sprite-studio/new" },
    ],
    owns: ["/agents/motion-director", "/motion-studio", "/sprite-studio"],
  },
];

export interface SecondaryNavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export const brainNavigation: SecondaryNavigationItem[] = [
  { label: "Memory", href: "/memory", icon: BrainCircuit },
  { label: "Story Library", href: "/story-library", icon: BookHeart },
  { label: "Used Storylines", href: "/used-storylines", icon: BookHeart },
  { label: "Examples", href: "/examples", icon: FileText },
  { label: "Failure Library", href: "/failures", icon: AlertTriangle },
  { label: "Knowledge Base", href: "/knowledge", icon: BookOpenText },
];

export const projectNavigation: SecondaryNavigationItem[] = [
  { label: "Generated Comics", href: "/projects/generated-comics", icon: FileText },
  { label: "Approved Comics", href: "/projects/approved-comics", icon: FileCheck2 },
  { label: "Exports", href: "/projects/exports", icon: Download },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function agentForPath(pathname: string): AgentDefinition | undefined {
  return agents.find(agent => agent.owns.some(path => path === "/" ? pathname === "/" : pathname.startsWith(path)));
}

export function agentById(id: string): AgentDefinition | undefined {
  const aliases: Record<string, CanonicalAgentId> = {
    content: "concept-generator",
    "content-agent": "concept-generator",
    "prompt-engineer": "prompt-agent",
    "social-learning": "social-intelligence",
    "art-reviewer": "art-review",
    "art-qa": "art-review",
    "brand-partnerships": "brand-integration",
    "motion-agent": "motion-director",
  };
  const normalized = aliases[id] ?? id;
  return agents.find(agent => agent.id === normalized);
}

export function validateAgentRegistry(): string[] {
  const problems: string[] = [];
  for (const id of canonicalAgentIds) {
    const agent = agents.find(item => item.id === id);
    if (!agent) problems.push(`Missing agent registry record: ${id}`);
    else if (!agent.avatarPath.startsWith("/agents/") || !agent.avatarPath.endsWith(".png")) problems.push(`Invalid portrait path for ${id}`);
  }
  return problems;
}
