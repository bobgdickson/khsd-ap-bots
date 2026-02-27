"use client";

import { useMsal } from "@azure/msal-react";
import { Bell, LogOut, ShieldCheck } from "lucide-react";

import { clearAuthCookie } from "@/auth/auth-cookie";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { getInitials } from "@/lib/utils";

export function AccountSwitcher() {
  const { instance, accounts } = useMsal();
  const account = instance.getActiveAccount() ?? accounts.at(0);

  const name = account?.name?.trim() ?? "Signed In User";
  const email = account?.username ?? "unknown@user";

  const handleLogout = async () => {
    clearAuthCookie();
    await instance.logoutRedirect();
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Avatar className="size-9 rounded-lg">
          <AvatarFallback className="rounded-lg">{getInitials(name)}</AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-56 space-y-1 rounded-lg" side="bottom" align="end" sideOffset={4}>
        <div className="px-2 py-1">
          <div className="truncate text-sm font-semibold">{name}</div>
          <div className="text-muted-foreground truncate text-xs">{email}</div>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem disabled>
            <ShieldCheck />
            Microsoft Entra
          </DropdownMenuItem>
          <DropdownMenuItem disabled>
            <Bell />
            Notifications
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => void handleLogout()}>
          <LogOut />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
