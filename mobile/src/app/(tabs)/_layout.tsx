import { Tabs } from 'expo-router';
import { Text, type ColorValue } from 'react-native';

import { useColors } from '../../components/ui';
import { useSession } from '../../lib/session';

function Glyph({ char, color }: { char: string; color: ColorValue }) {
  return <Text style={{ fontSize: 20, color }}>{char}</Text>;
}

export default function TabsLayout() {
  const c = useColors();
  const { pending } = useSession();
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: c.primary }}>
      <Tabs.Screen
        name="index"
        options={{ title: 'Capture', tabBarIcon: ({ color }) => <Glyph char="✎" color={color} /> }}
      />
      <Tabs.Screen
        name="inbox"
        options={{
          title: 'My ideas',
          tabBarBadge: pending.length || undefined,
          tabBarIcon: ({ color }) => <Glyph char="☰" color={color} />,
        }}
      />
      <Tabs.Screen
        name="products"
        options={{ title: 'Products', tabBarIcon: ({ color }) => <Glyph char="◫" color={color} /> }}
      />
      <Tabs.Screen
        name="settings"
        options={{ title: 'Settings', tabBarIcon: ({ color }) => <Glyph char="⚙" color={color} /> }}
      />
    </Tabs>
  );
}
