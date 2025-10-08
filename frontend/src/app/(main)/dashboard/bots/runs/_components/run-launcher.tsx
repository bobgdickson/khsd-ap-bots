"use client";

import * as React from "react";

import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api/client";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

import { runLaunchers } from "../config";

const CUSTOM_PROMPT_ID = "custom";

export function RunLauncher() {
  const router = useRouter();
  const launcher = runLaunchers[0];

  const instructionOptions = launcher.instructionOptions ?? [];
  const defaultVendor = launcher.vendorOptions[0]?.value ?? "";

  const [vendorKey, setVendorKey] = React.useState(defaultVendor);

  const getVendorDefaults = React.useCallback(
    (key: string) => {
      const vendor = launcher.vendorOptions.find((option) => option.value === key);
      const fallbackInstructionId = instructionOptions[0]?.id ?? "none";

      if (!vendor) {
        return {
          attachOnly: launcher.defaults.attach_only ?? false,
          rentLineEnabled: Boolean(launcher.defaults.rent_line),
          instructionId: fallbackInstructionId,
          apoOverride: "",
          apoEnabled: false,
        };
      }

      return {
        attachOnly: vendor.defaultAttachOnly ?? launcher.defaults.attach_only ?? false,
        rentLineEnabled: vendor.defaultRentLineEnabled ?? Boolean(launcher.defaults.rent_line),
        instructionId: vendor.defaultInstructionId ?? fallbackInstructionId,
        apoOverride: vendor.defaultApoOverride ?? "",
        apoEnabled: Boolean(vendor.defaultApoOverride),
      };
    },
    [instructionOptions, launcher],
  );

  const initialDefaults = React.useMemo(() => getVendorDefaults(defaultVendor), [defaultVendor, getVendorDefaults]);

  const [testMode, setTestMode] = React.useState(launcher.defaults.test_mode ?? true);
  const [attachOnly, setAttachOnly] = React.useState(initialDefaults.attachOnly ?? false);
  const [rentLineEnabled, setRentLineEnabled] = React.useState(initialDefaults.rentLineEnabled ?? false);
  const [rentLine, setRentLine] = React.useState(
    initialDefaults.rentLineEnabled ? launcher.defaults.rent_line ?? "" : "",
  );
  const [apoEnabled, setApoEnabled] = React.useState(initialDefaults.apoEnabled ?? false);
  const [apoOverride, setApoOverride] = React.useState(initialDefaults.apoOverride ?? "");

  const initialInstructionId = instructionOptions.some((option) => option.id === initialDefaults.instructionId)
    ? initialDefaults.instructionId
    : instructionOptions[0]?.id ?? CUSTOM_PROMPT_ID;

  const [selectedInstructionId, setSelectedInstructionId] = React.useState(initialInstructionId);
  const [instructions, setInstructions] = React.useState(() => {
    const match = instructionOptions.find((option) => option.id === initialInstructionId);
    return match?.prompt ?? "";
  });

  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (!rentLineEnabled) {
      setRentLine("");
    } else if (!rentLine && launcher.defaults.rent_line) {
      setRentLine(launcher.defaults.rent_line);
    }
  }, [rentLineEnabled, rentLine, launcher.defaults.rent_line]);

  React.useEffect(() => {
    if (selectedInstructionId === CUSTOM_PROMPT_ID) return;
    const match = instructionOptions.find((option) => option.id === selectedInstructionId);
    if (match) {
      setInstructions(match.prompt ?? "");
    }
  }, [selectedInstructionId, instructionOptions]);

  React.useEffect(() => {
    const defaults = getVendorDefaults(vendorKey);
    setAttachOnly(defaults.attachOnly ?? false);
    setRentLineEnabled(defaults.rentLineEnabled ?? false);
    setApoEnabled(defaults.apoEnabled ?? false);

    const fallbackId = instructionOptions[0]?.id ?? CUSTOM_PROMPT_ID;
    const nextInstructionId = defaults.instructionId ?? fallbackId;
    setSelectedInstructionId(
      instructionOptions.some((option) => option.id === nextInstructionId) ? nextInstructionId : CUSTOM_PROMPT_ID,
    );

    const selection = instructionOptions.find((option) => option.id === defaults.instructionId);
    setInstructions(selection?.prompt ?? "");
    setApoOverride(defaults.apoOverride ?? "");
  }, [vendorKey, getVendorDefaults, instructionOptions]);

  const handleApoToggle = React.useCallback(
    (value: boolean) => {
      setApoEnabled(value);
      if (!value) {
        setApoOverride("");
      } else {
        const defaults = getVendorDefaults(vendorKey);
        if (defaults.apoOverride) {
          setApoOverride(defaults.apoOverride);
        }
      }
    },
    [getVendorDefaults, vendorKey],
  );

  const handleSubmit = async () => {
    if (!vendorKey) {
      toast.error("Select a vendor to start a run");
      return;
    }

    setIsSubmitting(true);
    try {
      const { data: payload } = await apiClient.post(launcher.endpoint, {
        vendor_key: vendorKey,
        test_mode: testMode,
        rent_line: rentLineEnabled && rentLine ? rentLine : undefined,
        attach_only: attachOnly,
        additional_instructions: instructions.trim() ? instructions : undefined,
        apo_override: apoEnabled && apoOverride.trim() ? apoOverride.trim() : undefined,
      });

      const runid = payload?.runid ?? "";
      toast.success("Run scheduled", {
        description: runid ? `Run ${runid} queued successfully.` : "The run was queued successfully.",
      });
      if (selectedInstructionId === CUSTOM_PROMPT_ID) {
        setInstructions("");
      }
      router.refresh();
    } catch (error: any) {
      toast.error("Unable to schedule run", {
        description: error?.message ?? "Something went wrong while starting the run.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Launch {launcher.label}</CardTitle>
        <CardDescription>Queue a new run from the UI without opening the CLI.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="vendor">Vendor</Label>
          <Select value={vendorKey} onValueChange={setVendorKey}>
            <SelectTrigger id="vendor">
              <SelectValue placeholder="Select vendor" />
            </SelectTrigger>
            <SelectContent>
              {launcher.vendorOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <Switch id="test-mode" checked={testMode} onCheckedChange={setTestMode} />
          <Label htmlFor="test-mode">Run in test mode</Label>
        </div>

        <div className="flex items-center gap-2">
          <Switch id="attach-only" checked={attachOnly} onCheckedChange={setAttachOnly} />
          <Label htmlFor="attach-only">Attach only</Label>
        </div>

        {launcher.allowRentLine !== false && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Switch id="rent-line-toggle" checked={rentLineEnabled} onCheckedChange={setRentLineEnabled} />
              <Label htmlFor="rent-line-toggle">Specify rent line</Label>
            </div>
            {rentLineEnabled && (
              <Input
                id="rent-line"
                value={rentLine}
                onChange={(event) => setRentLine(event.target.value)}
                placeholder="FY26"
              />
            )}
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="instructions">Additional instructions</Label>
          <Select
            value={selectedInstructionId}
            onValueChange={(value) => {
              setSelectedInstructionId(value);
              if (value === CUSTOM_PROMPT_ID) return;
              const match = instructionOptions.find((option) => option.id === value);
              setInstructions(match?.prompt ?? "");
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select prompt" />
            </SelectTrigger>
            <SelectContent>
              {instructionOptions.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label}
                </SelectItem>
              ))}
              <SelectItem value={CUSTOM_PROMPT_ID}>Custom</SelectItem>
            </SelectContent>
          </Select>
          <Textarea
            id="instructions"
            value={instructions}
            onChange={(event) => {
              setSelectedInstructionId(CUSTOM_PROMPT_ID);
              setInstructions(event.target.value);
            }}
            placeholder="Optional guidance for the extraction agent"
            rows={3}
          />
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Switch id="apo-override-toggle" checked={apoEnabled} onCheckedChange={handleApoToggle} />
            <Label htmlFor="apo-override-toggle">Specify APO override</Label>
          </div>
          {apoEnabled && (
            <Input
              id="apo-override"
              value={apoOverride}
              onChange={(event) => setApoOverride(event.target.value)}
              placeholder="Optional APO override"
            />
          )}
        </div>

        <div className="flex justify-end">
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Starting..." : "Start Run"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
