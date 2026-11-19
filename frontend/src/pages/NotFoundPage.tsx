import { Button } from "@mantine/core";
import { IconCompass } from "@tabler/icons-react";
import { useNavigate } from "react-router";
import { EmptyBox } from "../components/ui";

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <EmptyBox
      icon={<IconCompass size={30} />}
      title="Page not found"
      text="This page doesn't exist. Let's get you back to your dashboard."
      action={<Button onClick={() => navigate("/app")}>Go to dashboard</Button>}
    />
  );
}
