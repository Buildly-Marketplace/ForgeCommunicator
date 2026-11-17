import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, View } from 'react-native';

import { Banner, Body, Button, Card, Empty, Screen } from '../components/ui';
import { useSession } from '../lib/session';
import type { Product } from '../lib/types';

/** Pick the product a free note belongs to, then upload & estimate it. */
export default function ChooseProduct() {
  const { clientId } = useLocalSearchParams<{ clientId: string }>();
  const { api, workspace, jottings, uploadJotting } = useSession();
  const [products, setProducts] = useState<Product[] | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const note = jottings.find((j) => j.clientId === clientId);

  useEffect(() => {
    if (!workspace) return;
    api
      .products(workspace.id)
      .then(setProducts)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [api, workspace]);

  async function pick(product: Product) {
    setBusy(product.id);
    setError(null);
    try {
      const idea = await uploadJotting(clientId, product.id);
      if (idea) router.replace({ pathname: '/idea/[id]', params: { id: String(idea.id), refine: '1' } });
      else router.back(); // queued offline; it shows in My ideas
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  if (!workspace) {
    return (
      <Screen style={{ padding: 16 }}>
        <Banner text="Join a workspace first — ideas belong to a product in a workspace." />
      </Screen>
    );
  }

  return (
    <Screen>
      <FlatList
        data={products ?? []}
        keyExtractor={(p) => String(p.id)}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        ListHeaderComponent={
          <View style={{ gap: 10 }}>
            {note ? (
              <Body muted numberOfLines={3}>
                “{note.body || `${note.photos.length} photo(s)`}”
              </Body>
            ) : null}
            <Body style={{ fontWeight: '700' }}>Which product is this for?</Body>
            {error ? <Banner tone="danger" text={error} /> : null}
            {products === null && !error ? <ActivityIndicator /> : null}
          </View>
        }
        ListEmptyComponent={
          products === null ? undefined : (
            <View style={{ gap: 10 }}>
              <Empty title="No products yet" hint="Sync your products from Buildly Labs first." />
              <Button title="Go to Products" variant="secondary" onPress={() => router.replace('/products')} />
            </View>
          )
        }
        renderItem={({ item }) => (
          <Pressable accessibilityRole="button" disabled={busy !== null} onPress={() => pick(item)}>
            <Card style={item.color ? { borderLeftWidth: 4, borderLeftColor: item.color } : undefined}>
              <Body style={{ fontWeight: '700' }}>{item.name}</Body>
              {item.description ? (
                <Body muted numberOfLines={2}>
                  {item.description}
                </Body>
              ) : null}
              {busy === item.id ? <ActivityIndicator /> : null}
            </Card>
          </Pressable>
        )}
      />
    </Screen>
  );
}
