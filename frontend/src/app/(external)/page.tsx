import { redirect } from "next/navigation";

export default function Home() {
  redirect("/dashboard/bots");
  return <>Coming Soon</>;
}
