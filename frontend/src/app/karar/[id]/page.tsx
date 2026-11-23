import { DecisionView } from "@/components/DecisionView";

export const metadata = { title: "Karar — İçtihat Arama" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DecisionView id={Number(id)} />;
}
