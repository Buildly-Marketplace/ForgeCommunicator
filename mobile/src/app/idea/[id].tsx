import { Stack, router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Image, Pressable, ScrollView, View } from 'react-native';

import { BUILDER_LABEL, Banner, Body, Button, Card, Chip, Label, Row, STATUS_LABEL, Screen, useColors } from '../../components/ui';
import { ApiError } from '../../lib/api';
import { useSession } from '../../lib/session';
import type { Agent, Builder, BreakdownItem, Idea, SubmitResult } from '../../lib/types';

const TYPE_ICON: Record<string, string> = { feature: '✨', issue: '🐞', task: '☑' };
const BUILDERS: Builder[] = ['ai', 'pair', 'dev'];

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <View style={{ flex: 1, alignItems: 'center' }}>
      <Body style={{ fontSize: 22, fontWeight: '800' }}>{value}</Body>
      <Body muted style={{ fontSize: 12 }}>
        {label}
      </Body>
    </View>
  );
}

function ItemCard({
  item,
  locked,
  onChange,
}: {
  item: BreakdownItem;
  locked: boolean;
  onChange: (patch: { selected?: boolean; builder?: Builder }) => void;
}) {
  const [open, setOpen] = useState(false);
  const est = item.estimate;
  return (
    <Card style={!item.selected ? { opacity: 0.55 } : undefined}>
      <Pressable onPress={() => setOpen(!open)} accessibilityRole="button" accessibilityHint="Show details">
        <Body style={{ fontWeight: '700' }}>
          {TYPE_ICON[item.type]} {item.title}
        </Body>
        <Body muted style={{ fontSize: 13 }}>
          {est.points} pts · Dev ~{est.human_hours}h · AI ~{est.ai_hours}h · {item.priority} priority
        </Body>
      </Pressable>
      {open ? (
        <View style={{ gap: 6 }}>
          {item.description ? <Body>{item.description}</Body> : null}
          {item.acceptance_criteria.map((ac) => (
            <Body key={ac} muted>
              ☐ {ac}
            </Body>
          ))}
          {item.rationale ? <Body muted style={{ fontStyle: 'italic' }}>{item.rationale}</Body> : null}
        </View>
      ) : null}
      {!locked ? (
        <Row>
          <Chip
            label={item.selected ? '✓ Include' : 'Skipped'}
            active={item.selected}
            onPress={() => onChange({ selected: !item.selected })}
          />
          <Body muted style={{ fontSize: 13 }}>Built by:</Body>
          {BUILDERS.map((b) => (
            <Chip key={b} label={BUILDER_LABEL[b]} active={item.builder === b} onPress={() => onChange({ builder: b })} />
          ))}
        </Row>
      ) : (
        <Row>
          <Chip label={BUILDER_LABEL[item.builder]} />
        </Row>
      )}
    </Card>
  );
}

/** Show the error, or open the paywall if the server says Pro is needed. */
function handleError(e: unknown, setError: (m: string) => void, refreshAccess: () => Promise<unknown>) {
  if (e instanceof ApiError && e.needsSubscription) {
    refreshAccess().catch(() => undefined);
    router.push('/paywall');
    return;
  }
  setError(e instanceof Error ? e.message : String(e));
}

export default function IdeaDetail() {
  const c = useColors();
  const { id, refine } = useLocalSearchParams<{ id: string; refine?: string }>();
  const { api, refreshAccess } = useSession();
  const [idea, setIdea] = useState<Idea | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState<number | null>(null);
  const [busy, setBusy] = useState<'refine' | 'submit' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SubmitResult | null>(null);
  const autoRefined = useRef(false);

  const runRefine = useCallback(async () => {
    setBusy('refine');
    setError(null);
    try {
      setIdea(await api.refineIdea(Number(id)));
    } catch (e) {
      handleError(e, setError, refreshAccess);
    } finally {
      setBusy(null);
    }
  }, [api, id, refreshAccess]);

  useEffect(() => {
    (async () => {
      try {
        const loaded = await api.idea(Number(id));
        setIdea(loaded);
        api.agents(loaded.workspace_id).then(setAgents).catch(() => undefined);
        if (refine === '1' && !loaded.breakdown && loaded.status !== 'submitted' && !autoRefined.current) {
          autoRefined.current = true;
          runRefine();
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [api, id, refine, runRefine]);

  async function patchItem(itemId: string, patch: { selected?: boolean; builder?: Builder }) {
    if (!idea?.breakdown) return;
    // Optimistic update, then reconcile with the server's totals
    const items = idea.breakdown.items.map((i) => (i.id === itemId ? { ...i, ...patch } : i));
    setIdea({ ...idea, breakdown: { ...idea.breakdown, items } });
    try {
      setIdea(await api.updateIdea(idea.id, { items: [{ id: itemId, ...patch }] }));
    } catch (e) {
      handleError(e, setError, refreshAccess);
    }
  }

  async function send() {
    if (!idea) return;
    setBusy('submit');
    setError(null);
    try {
      const res = await api.submitIdea(idea.id, { push_to_labs: true, agent_integration_id: agentId });
      setResult(res);
      setIdea(res.idea);
    } catch (e) {
      handleError(e, setError, refreshAccess);
    } finally {
      setBusy(null);
    }
  }

  function confirmDelete() {
    if (!idea) return;
    Alert.alert('Delete this capture?', 'Items already sent to Labs are not affected.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          await api.deleteIdea(idea.id).catch(() => undefined);
          router.back();
        },
      },
    ]);
  }

  if (!idea) {
    return (
      <Screen style={{ alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        {error ? <Banner tone="danger" text={error} /> : <ActivityIndicator />}
      </Screen>
    );
  }

  const bd = idea.breakdown;
  const submitted = idea.status === 'submitted';
  const selected = bd?.items.filter((i) => i.selected) ?? [];
  const wantsAgent = selected.some((i) => i.builder !== 'dev');

  return (
    <Screen>
      <Stack.Screen options={{ title: STATUS_LABEL[idea.status] ?? 'Idea' }} />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }}>
        <Card>
          <Label>
            {idea.kind}
            {idea.product_name ? ` · ${idea.product_name}` : ''}
          </Label>
          {idea.title ? <Body style={{ fontWeight: '700', fontSize: 18 }}>{idea.title}</Body> : null}
          {idea.body ? <Body>{idea.body}</Body> : null}
          {idea.attachments.length ? (
            <ScrollView horizontal contentContainerStyle={{ gap: 8 }}>
              {idea.attachments.map((a) => (
                <Image key={a.url} source={{ uri: a.url }} style={{ width: 96, height: 96, borderRadius: 10 }} />
              ))}
            </ScrollView>
          ) : null}
        </Card>

        {error ? <Banner tone="danger" text={error} /> : null}
        {idea.error && idea.status === 'failed' ? <Banner tone="danger" text={idea.error} /> : null}

        {busy === 'refine' ? (
          <Card style={{ alignItems: 'center' }}>
            <ActivityIndicator />
            <Body muted>Breaking it down into features, issues and estimates…</Body>
          </Card>
        ) : null}

        {!bd && !busy && !submitted ? (
          <Button title="✨ Estimate with AI" onPress={runRefine} />
        ) : null}

        {bd ? (
          <>
            {bd.summary ? <Body muted>{bd.summary}</Body> : null}
            <Card>
              <Row style={{ flexWrap: 'nowrap' }}>
                <Stat value={String(bd.totals.points)} label="story points" />
                <Stat value={`${bd.totals.human_hours}h`} label="developer" />
                <Stat value={`${bd.totals.ai_hours}h`} label="AI agent" />
              </Row>
              <Body muted style={{ fontSize: 12, textAlign: 'center' }}>
                {bd.engine === 'heuristic' ? 'Rough estimate — no AI configured on the server' : `Estimated by ${bd.engine}`}
              </Body>
            </Card>

            <Label>{bd.items.length} item(s) — tap for details</Label>
            {bd.items.map((item) => (
              <ItemCard key={item.id} item={item} locked={submitted} onChange={(p) => patchItem(item.id, p)} />
            ))}

            {bd.questions.length ? (
              <Card>
                <Label>Open questions</Label>
                {bd.questions.map((q) => (
                  <Body key={q}>• {q}</Body>
                ))}
              </Card>
            ) : null}
          </>
        ) : null}

        {bd && !submitted ? (
          <>
            {wantsAgent && agents.length ? (
              <View style={{ gap: 8 }}>
                <Label>Hand AI work to an agent (optional)</Label>
                <Row>
                  <Chip label="No agent yet" active={agentId === null} onPress={() => setAgentId(null)} />
                  {agents.map((a) => (
                    <Chip
                      key={a.id}
                      label={`${a.avatar_emoji ?? '🤖'} ${a.name}`}
                      active={agentId === a.id}
                      onPress={() => setAgentId(a.id)}
                    />
                  ))}
                </Row>
              </View>
            ) : null}
            <Button
              title={`Send ${selected.length} item(s) to Labs`}
              onPress={send}
              loading={busy === 'submit'}
              disabled={!!busy || selected.length === 0}
            />
            <Button title="Re-estimate" variant="ghost" onPress={runRefine} disabled={!!busy} />
          </>
        ) : null}

        {submitted ? (
          <Card>
            <Label>Sent</Label>
            {(result?.created ?? idea.submitted_items).map((s) => (
              <Body key={s.artifact_id}>
                {TYPE_ICON[s.type]} {s.title}
                {s.labs_uuid ? '  ✓ Labs' : ''}
                {s.assigned_agent ? `  → 🤖 ${s.assigned_agent}` : ''}
              </Body>
            ))}
            {result?.warnings.map((w) => (
              <Body key={w} style={{ color: c.warn }}>
                {w}
              </Body>
            ))}
          </Card>
        ) : null}

        <Button title="Delete capture" variant="ghost" onPress={confirmDelete} />
      </ScrollView>
    </Screen>
  );
}
