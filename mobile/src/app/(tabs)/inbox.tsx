import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { FlatList, Pressable, RefreshControl, View } from 'react-native';

import { Banner, Body, Card, Chip, Empty, Row, STATUS_LABEL, Screen } from '../../components/ui';
import { useSession } from '../../lib/session';
import type { Idea } from '../../lib/types';

const KIND_ICON: Record<string, string> = { idea: '💡', bug: '🐞', feedback: '💬' };
const STATUS_TONE: Record<string, 'success' | 'warn' | 'danger' | undefined> = {
  submitted: 'success',
  refined: 'warn',
  failed: 'danger',
};

export default function Inbox() {
  const { api, workspace, pending, flush } = useSession();
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (pending.length) await flush();
      setIdeas(await api.ideas(workspace?.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, workspace?.id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  return (
    <Screen>
      <FlatList
        data={ideas}
        keyExtractor={(i) => String(i.id)}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListHeaderComponent={
          <View style={{ gap: 10 }}>
            {error ? <Banner tone="danger" text={error} /> : null}
            {pending.map((p) => (
              <Card key={p.clientId}>
                <Body numberOfLines={2}>
                  {KIND_ICON[p.kind]} {p.body || `${p.photos.length} photo(s)`}
                </Body>
                <Row>
                  <Chip label="Waiting to upload" tone="warn" />
                  {p.lastError ? <Body muted numberOfLines={1}>{p.lastError}</Body> : null}
                </Row>
              </Card>
            ))}
          </View>
        }
        ListEmptyComponent={
          loading || pending.length ? undefined : (
            <Empty title="No captures yet" hint="Ideas and bugs you jot down on the Capture tab show up here." />
          )
        }
        renderItem={({ item }) => {
          const bd = item.breakdown;
          return (
            <Pressable
              accessibilityRole="button"
              onPress={() => router.push({ pathname: '/idea/[id]', params: { id: String(item.id) } })}
            >
              <Card>
                <Body style={{ fontWeight: '700' }} numberOfLines={2}>
                  {KIND_ICON[item.kind]} {item.title || item.body || 'Photo capture'}
                </Body>
                {item.title && item.body ? (
                  <Body muted numberOfLines={2}>
                    {item.body}
                  </Body>
                ) : null}
                <Row>
                  <Chip label={STATUS_LABEL[item.status] ?? item.status} tone={STATUS_TONE[item.status]} />
                  {item.product_name ? <Chip label={item.product_name} /> : null}
                  {bd ? <Chip label={`${bd.items.length} items · ${bd.totals.points} pts`} /> : null}
                  {item.attachments.length ? <Chip label={`📎 ${item.attachments.length}`} /> : null}
                </Row>
              </Card>
            </Pressable>
          );
        }}
      />
    </Screen>
  );
}
