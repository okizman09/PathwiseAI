import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, Clock, MoreVertical, Pencil, Trash2 } from "lucide-react";
import { useState, useEffect } from "react";
import { toast } from "sonner";

import { AppHeader } from "@/components/AppHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { api, type WorkflowListResponse } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export const Route = createFileRoute("/app_/history")({
  component: HistoryPage,
});

function HistoryPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [session, setSession] = useState<any>(null);

  useEffect(() => {
    api.getMe().then((me) => {
      setSession({ ...me, access_token: "" });
    }).catch((e) => {
      console.error(e);
      window.location.href = "/login";
    });
  }, []);

  const { data: workflows, isLoading, isError } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api.getWorkflows(0, 50),
    enabled: !!session,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteWorkflow(id),
    onSuccess: () => {
      toast.success("Workflow deleted");
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
    onError: () => {
      toast.error("Failed to delete workflow");
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, title }: { id: number, title: string }) => api.updateWorkflow(id, { title }),
    onSuccess: () => {
      toast.success("Workflow renamed");
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
    onError: () => {
      toast.error("Failed to rename workflow");
    }
  });

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");

  if (!session) return <div className="p-8 text-center text-muted-foreground">Loading session...</div>;

  return (
    <div className="min-h-screen bg-background">
      <AppHeader session={session as any} />
      <main className="mx-auto max-w-[960px] px-5 py-12 sm:px-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <Button variant="ghost" size="sm" asChild className="mb-4 text-muted-foreground -ml-2">
              <Link to="/app" className="gap-2">
                <ArrowLeft className="size-4" />
                Back to Workspace
              </Link>
            </Button>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">History</h1>
            <p className="mt-2 text-muted-foreground">
              Your saved creation paths and workflows.
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="py-12 text-center text-muted-foreground">Loading history...</div>
        ) : isError ? (
          <div className="py-12 text-center text-destructive">Failed to load history.</div>
        ) : workflows?.length === 0 ? (
          <Card className="border-dashed shadow-none">
            <CardContent className="flex flex-col items-center justify-center py-20 text-center">
              <Clock className="mb-4 size-8 text-muted-foreground/50" />
              <h3 className="text-lg font-medium text-foreground">No workflows yet</h3>
              <p className="mt-1 text-sm text-muted-foreground max-w-sm">
                Paths you create in the workspace will automatically be saved here.
              </p>
              <Button asChild className="mt-6" variant="outline">
                <Link to="/app">Go to Workspace</Link>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {workflows?.map((w) => (
              <Card key={w.id} className="transition-all hover:border-primary/30">
                <CardContent className="flex items-center justify-between p-4 sm:p-6">
                  <div className="grid gap-1">
                    {editingId === w.id ? (
                      <div className="flex items-center gap-2">
                        <Input
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          className="h-8 w-64 text-base font-semibold"
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              updateMutation.mutate({ id: w.id, title: editTitle });
                              setEditingId(null);
                            } else if (e.key === "Escape") {
                              setEditingId(null);
                            }
                          }}
                        />
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            updateMutation.mutate({ id: w.id, title: editTitle });
                            setEditingId(null);
                          }}
                        >
                          Save
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setEditingId(null)}
                        >
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <CardTitle className="text-base sm:text-lg">
                        <Link to={`/app`} search={{ load: w.id }} className="hover:underline">
                          {w.title}
                        </Link>
                      </CardTitle>
                    )}
                    <CardDescription>
                      {new Date(w.created_at).toLocaleString()}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="secondary" size="sm" asChild className="hidden sm:flex">
                      <Link to={`/app`} search={{ load: w.id }}>
                        Open
                      </Link>
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="size-8">
                          <MoreVertical className="size-4" />
                          <span className="sr-only">Open menu</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => {
                            setEditingId(w.id);
                            setEditTitle(w.title);
                          }}
                        >
                          <Pencil className="mr-2 size-4" />
                          Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive"
                          onClick={() => {
                            if (confirm("Are you sure you want to delete this workflow?")) {
                              deleteMutation.mutate(w.id);
                            }
                          }}
                        >
                          <Trash2 className="mr-2 size-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
