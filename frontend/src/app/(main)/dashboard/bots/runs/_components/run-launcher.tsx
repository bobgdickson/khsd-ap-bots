
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

  const vendorDefault = launcher.vendorOptions[0]?.value ?? "";
  const instructionOptions = launcher.instructionOptions ?? [];

  const [vendorKey, setVendorKey] = React.useState(vendorDefault);
  const [testMode, setTestMode] = React.useState(launcher.defaults.test_mode ?? true);
  const [attachOnly, setAttachOnly] = React.useState(launcher.defaults.attach_only ?? false);
  const [rentLineEnabled, setRentLineEnabled] = React.useState(Boolean(launcher.defaults.rent_line));
  const [rentLine, setRentLine] = React.useState(launcher.defaults.rent_line ?? "");
  const [selectedInstructionId, setSelectedInstructionId] = React.useState(
    instructionOptions[0]?.id ?? CUSTOM_PROMPT_ID,
  );
  const [instructions, setInstructions] = React.useState(() => instructionOptions[0]?.prompt ?? "");
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

        <div className="flex justify-end">
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Starting..." : "Start Run"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
