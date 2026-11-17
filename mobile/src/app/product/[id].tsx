import { Stack, router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, View } from 'react-native';

import { Banner, Body, Button, Card, Chip, Empty, Row, Screen } from '../../components/ui';
import { useSession } from '../../lib/session';
import type { BacklogItem } from '../../lib/types';

const FILTERS = [
  { key: undefined, label: 'All' },
  { key: 'feature', label: '✨ Features' },
  { key: 'issue', label: '🐞 Issues' },
  { key: 'task', label: '☑ Tasks' },
] as const;

const DONE = new Set(['closed', 'done', 'shipped', 'wont_fix', 'rejected']);

export default function ProductDetail() {
  const { id, name } = useLocalSearchParams<{ id: string; name?: string }>();
  const { api } = useSession();
  const [filter, setFilter] = useState<string | undefined>(undefined);
  const [items, setItems] = useState<BacklogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await api.productItems(Number(id), filter));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [api, id, filter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Screen>
      <Stack.Screen options={{ title: name ?? 'Product' }} />
      <FlatList
        data={items}
        keyExtractor={(i) => String(i.id)}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListHeaderComponent={
          <View style={{ gap: 10 }}>
            <Row>
              {FILTERS.map((f) => (
                <Chip key={f.label} label={f.label} active={filter === f.key} onPress={() => setFilter(f.key)} />
              ))}
            </Row>
            <Button title="✎ Capture an idea for this product" variant="secondary" onPress={() => router.navigate('/')} />
            {error ? <Banner tone="danger" text={error} /> : null}
          </View>
        }
        ListEmptyComponent={loading ? undefined : <Empty title="Nothing here yet" />}
        renderItem={({ item }) => (
          <Card style={DONE.has(item.status) ? { opacity: 0.6 } : undefined}>
            <Body style={{ fontWeight: '600' }}>{item.title}</Body>
            <Row>
              <Chip label={item.type} />
              <Chip label={item.status.replace('_', ' ')} tone={DONE.has(item.status) ? 'success' : undefined} />
              {item.priority ? <Chip label={item.priority} tone={item.priority === 'urgent' ? 'danger' : undefined} /> : null}
              {item.assignee_agent ? <Chip label={`🤖 ${item.assignee_agent}`} /> : null}
              {item.labs_uuid ? <Chip label="Labs" tone="success" /> : null}
            </Row>
          </Card>
        )}
      />
    </Screen>
  );
}
