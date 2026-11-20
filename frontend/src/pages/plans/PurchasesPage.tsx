import { Tabs } from "@mantine/core";
import { IconBuildingStore, IconHistory, IconShoppingCart } from "@tabler/icons-react";
import { useSearchParams } from "react-router";
import { Explorer } from "../../components/Explorer";
import { PageHeader } from "../../components/ui";
import { DealersTable } from "../sales/ContactsTables";
import PlansListPage from "./PlansListPage";

export default function PurchasesPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "plan";
  return (
    <>
      <PageHeader title="Purchases" subtitle="What to buy next, your dealers, and everything you bought." />
      <Tabs value={tab} onChange={(v) => setParams({ tab: v ?? "plan" })} keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="plan" leftSection={<IconShoppingCart size={16} />}>Purchase plan</Tabs.Tab>
          <Tabs.Tab value="dealers" leftSection={<IconBuildingStore size={16} />}>Dealers</Tabs.Tab>
          <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>Purchase history</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="plan"><PlansListPage embedded /></Tabs.Panel>
        <Tabs.Panel value="dealers"><DealersTable /></Tabs.Panel>
        <Tabs.Panel value="history"><Explorer kind="purchases" initialGroup="dealer" initialRange="Last 3 months" /></Tabs.Panel>
      </Tabs>
    </>
  );
}
