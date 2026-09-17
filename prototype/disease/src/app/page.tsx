import Dashboard from "@/components/dashboard";
import { getDataset } from "@/lib/dataset";

export const dynamic = "force-dynamic";

export default async function Home() {
  const dataset = await getDataset();
  return (
    <Dashboard
      initialDataset={dataset}
      aiEnabled={Boolean(process.env.GEMINI_API_KEY)}
      accessTokenRequired={Boolean(process.env.ANALYSIS_ACCESS_TOKEN)}
    />
  );
}
