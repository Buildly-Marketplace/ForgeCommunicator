import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { FlatList, Pressable, RefreshControl, View } from 'react-native';

import { Banner, Body, Button, Card, Chip, Empty, Row, Screen } from '../../components/ui';
import { useSession } from '../../lib/session';
import type { Product } from '../../lib/types';

export default function Products() {
  const { api, workspace } = useSession();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<{ text: string; tone: 'danger' | 'success' } | null>(null);

  const load = useCallback(async () => {
    if (!workspace) return;
    setLoading(true);
    try {
      setProducts(await api.products(workspace.id));
    } catch (e) {
      setMessage({ text: e instanceof Error ? e.message : String(e), tone: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [api, workspace]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  async function sync() {
    if (!workspace) return;
    setSyncing(true);
    setMessage(null);
    try {
      await api.syncProducts(workspace.id);
      await load();
      setMessage({ text: 'Synced with Buildly Labs.', tone: 'success' });
    } catch (e) {
      setMessage({ text: e instanceof Error ? e.message : String(e), tone: 'danger' });
    } finally {
      setSyncing(false);
    }
  }

  return (
    <Screen>
      <FlatList
        data={products}
        keyExtractor={(p) => String(p.id)}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListHeaderComponent={
          <View style={{ gap: 10 }}>
            {workspace && !workspace.labs_connected ? (
              <Banner text="This workspace isn’t connected to Buildly Labs yet. Sign in with Labs, or ask an admin to connect it in workspace settings." />
            ) : null}
            <Button title="↻ Sync from Labs" variant="secondary" onPress={sync} loading={syncing} />
            {message ? <Banner tone={message.tone} text={message.text} /> : null}
          </View>
        }
        ListEmptyComponent={
          loading ? undefined : <Empty title="No products" hint="Sync from Labs to pull in your products and backlog." />
        }
        renderItem={({ item }) => (
          <Pressable
            accessibilityRole="button"
            onPress={() =>
              router.push({ pathname: '/product/[id]', params: { id: String(item.id), name: item.name } })
            }
          >
            <Card style={item.color ? { borderLeftWidth: 4, borderLeftColor: item.color } : undefined}>
              <Body style={{ fontWeight: '700', fontSize: 17 }}>{item.name}</Body>
              {item.description ? (
                <Body muted numberOfLines={2}>
                  {item.description}
                </Body>
              ) : null}
              <Row>
                <Chip label={`✨ ${item.open_features} features`} />
                <Chip label={`🐞 ${item.open_issues} issues`} tone={item.open_issues ? 'warn' : undefined} />
                {item.labs_uuid ? <Chip label="Labs" tone="success" /> : null}
              </Row>
            </Card>
          </Pressable>
        )}
      />
    </Screen>
  );
}
