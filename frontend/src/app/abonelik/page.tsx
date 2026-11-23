import { SubscriptionView } from "@/components/SubscriptionView";

export const metadata = { title: "Abonelik — İçtihat Arama" };

export default async function Page({ searchParams }: { searchParams: Promise<{ durum?: string }> }) {
  const { durum } = await searchParams;
  return <SubscriptionView result={durum ?? null} />;
}
