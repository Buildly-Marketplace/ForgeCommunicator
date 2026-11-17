import type { ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  useColorScheme,
  type StyleProp,
  type TextInputProps,
  type ViewStyle,
} from 'react-native';

const light = {
  bg: '#F6F7FB',
  card: '#FFFFFF',
  text: '#0E1325',
  muted: '#5B6478',
  border: '#E2E5EE',
  primary: '#4F46E5',
  primaryText: '#FFFFFF',
  danger: '#DC2626',
  success: '#059669',
  warn: '#B45309',
  chip: '#EEF0F7',
};
const dark: typeof light = {
  bg: '#0B1020',
  card: '#141A2E',
  text: '#EEF1FA',
  muted: '#98A1B8',
  border: '#252D47',
  primary: '#7C83FF',
  primaryText: '#0B1020',
  danger: '#F87171',
  success: '#34D399',
  warn: '#FBBF24',
  chip: '#1E2640',
};
export type Palette = typeof light;

export function useColors(): Palette {
  return useColorScheme() === 'dark' ? dark : light;
}

export function Screen({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const c = useColors();
  return <View style={[{ flex: 1, backgroundColor: c.bg }, style]}>{children}</View>;
}

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const c = useColors();
  return (
    <View style={[styles.card, { backgroundColor: c.card, borderColor: c.border }, style]}>{children}</View>
  );
}

export function Title({ children }: { children: ReactNode }) {
  const c = useColors();
  return <Text style={[styles.title, { color: c.text }]}>{children}</Text>;
}

export function Body({
  children,
  muted,
  style,
  numberOfLines,
}: {
  children: ReactNode;
  muted?: boolean;
  style?: object;
  numberOfLines?: number;
}) {
  const c = useColors();
  return (
    <Text numberOfLines={numberOfLines} style={[styles.body, { color: muted ? c.muted : c.text }, style]}>
      {children}
    </Text>
  );
}

export function Label({ children }: { children: ReactNode }) {
  const c = useColors();
  return <Text style={[styles.label, { color: c.muted }]}>{children}</Text>;
}

export function Button({
  title,
  onPress,
  variant = 'primary',
  loading,
  disabled,
  style,
  accessibilityLabel,
}: {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  loading?: boolean;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
  accessibilityLabel?: string;
}) {
  const c = useColors();
  const bg =
    variant === 'primary' ? c.primary : variant === 'secondary' ? c.chip : variant === 'danger' ? c.danger : 'transparent';
  const fg = variant === 'primary' ? c.primaryText : variant === 'danger' ? '#fff' : c.primary;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? title}
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: bg, opacity: disabled ? 0.5 : pressed ? 0.8 : 1 },
        style,
      ]}
    >
      {loading ? <ActivityIndicator color={fg} /> : <Text style={[styles.buttonText, { color: fg }]}>{title}</Text>}
    </Pressable>
  );
}

export function Field(props: TextInputProps) {
  const c = useColors();
  return (
    <TextInput
      placeholderTextColor={c.muted}
      {...props}
      style={[styles.input, { color: c.text, backgroundColor: c.card, borderColor: c.border }, props.style]}
    />
  );
}

export function Chip({
  label,
  active,
  onPress,
  tone,
}: {
  label: string;
  active?: boolean;
  onPress?: () => void;
  tone?: 'success' | 'warn' | 'danger';
}) {
  const c = useColors();
  const toneColor = tone ? c[tone] : null;
  return (
    <Pressable
      accessibilityRole={onPress ? 'button' : 'text'}
      accessibilityState={onPress ? { selected: !!active } : undefined}
      onPress={onPress}
      disabled={!onPress}
      style={[
        styles.chip,
        {
          backgroundColor: active ? c.primary : c.chip,
          borderColor: toneColor ?? (active ? c.primary : c.border),
        },
      ]}
    >
      <Text style={{ color: active ? c.primaryText : (toneColor ?? c.text), fontSize: 13, fontWeight: '600' }}>
        {label}
      </Text>
    </Pressable>
  );
}

export function Row({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }, style]}>{children}</View>;
}

export function Banner({ text, tone = 'warn' }: { text: string; tone?: 'warn' | 'danger' | 'success' }) {
  const c = useColors();
  return (
    <View style={[styles.banner, { borderColor: c[tone] }]}>
      <Text style={{ color: c[tone], fontSize: 14 }}>{text}</Text>
    </View>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <View style={{ alignItems: 'center', padding: 32, gap: 6 }}>
      <Body style={{ fontWeight: '600' }}>{title}</Body>
      {hint ? <Body muted style={{ textAlign: 'center' }}>{hint}</Body> : null}
    </View>
  );
}

export const STATUS_LABEL: Record<string, string> = {
  draft: 'Draft',
  refining: 'Estimating…',
  refined: 'Ready to send',
  submitted: 'Sent to Labs',
  failed: 'Needs retry',
};

export const BUILDER_LABEL: Record<string, string> = { dev: 'Developer', ai: 'AI agent', pair: 'AI + Dev' };

const styles = StyleSheet.create({
  card: { borderRadius: 14, borderWidth: StyleSheet.hairlineWidth, padding: 14, gap: 8 },
  title: { fontSize: 22, fontWeight: '700' },
  body: { fontSize: 15, lineHeight: 21 },
  label: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.6 },
  button: { minHeight: 46, borderRadius: 12, paddingHorizontal: 16, alignItems: 'center', justifyContent: 'center' },
  buttonText: { fontSize: 16, fontWeight: '700' },
  input: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, borderWidth: 1 },
  banner: { borderWidth: 1, borderRadius: 12, padding: 12 },
});
