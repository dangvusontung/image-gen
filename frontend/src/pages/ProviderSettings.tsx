import { ArrowLeftIcon, ExternalLinkIcon, PlugZapIcon } from 'lucide-react'
import { useProviders, useSpend, useTestProvider, type ProviderInfo } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatUsd, MODEL_STATUS_LABEL, providerStatus } from '@/lib/providers'

const KEY_ENV: Record<string, string> = { gemini: 'GEMINI_API_KEY', bfl: 'BFL_API_KEY' }

export default function ProviderSettings({ onBack }: { onBack: () => void }) {
  const providers = useProviders()
  const spend = useSpend()

  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      <Button variant="ghost" onClick={onBack} className="mb-4">
        <ArrowLeftIcon /> Tất cả dự án
      </Button>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Nhà cung cấp & model</h1>
          <p className="mt-1 text-muted-foreground">
            API key chỉ nằm ở máy chủ (file <code>.env</code>), không bao giờ gửi tới trình duyệt. Sửa <code>.env</code> xong
            cần khởi động lại backend.
          </p>
        </div>
        {spend.data && (
          <Badge variant="outline" className="h-8 px-3 text-sm">
            Chi tiêu 24h (ước tính): ${spend.data.spent_24h_usd.toFixed(2)} / ${spend.data.limit_usd.toFixed(2)}
          </Badge>
        )}
      </header>

      {providers.isPending && <Skeleton className="h-96 rounded-xl" />}
      {providers.error && <ErrorAlert title="Không tải được danh sách nhà cung cấp" error={providers.error} />}
      <div className="grid gap-6">
        {providers.data?.map((p) => <ProviderCard key={p.name} provider={p} />)}
      </div>
    </main>
  )
}

function ProviderCard({ provider }: { provider: ProviderInfo }) {
  const test = useTestProvider()
  const status = providerStatus(provider)
  const env = KEY_ENV[provider.name]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          {provider.display_name}
          <Badge variant={status.tone === 'ok' ? 'default' : status.tone === 'warn' ? 'secondary' : 'outline'}>
            {status.label}
          </Badge>
        </CardTitle>
        {provider.data_notice && <CardDescription>{provider.data_notice}</CardDescription>}
        <CardAction className="flex gap-2">
          {provider.info_url && (
            <Button variant="ghost" size="sm" asChild>
              <a href={provider.info_url} target="_blank" rel="noreferrer noopener">
                Tài liệu <ExternalLinkIcon />
              </a>
            </Button>
          )}
          {provider.selectable && (
            <Button variant="outline" size="sm" onClick={() => test.mutate(provider.name)} disabled={test.isPending}>
              <PlugZapIcon /> {test.isPending ? 'Đang kiểm tra…' : 'Kiểm tra kết nối'}
            </Button>
          )}
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-4">
        {!provider.key_configured && env && (
          <p className="text-sm text-muted-foreground">
            Thêm <code className="rounded bg-muted px-1">{env}=…</code> vào <code>.env</code> ở thư mục gốc rồi khởi động lại
            backend.
          </p>
        )}
        {test.data && (
          <p role="status" className={test.data.ok ? 'text-sm text-emerald-700' : 'text-sm text-destructive'}>
            {test.data.message}
          </p>
        )}
        {test.error && <ErrorAlert title="Kiểm tra kết nối thất bại" error={test.error} />}
        {provider.models.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Model</TableHead>
                <TableHead>Ảnh tham chiếu tối đa</TableHead>
                <TableHead>Tỉ lệ khung</TableHead>
                <TableHead>Giá ước tính/ảnh</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {provider.models.map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="align-top whitespace-normal">
                    <div className="flex flex-wrap items-center gap-1.5 font-medium">
                      {m.display_name}
                      {m.default && <Badge variant="secondary">Mặc định</Badge>}
                      {m.status !== 'ga' && <Badge variant="outline">{MODEL_STATUS_LABEL[m.status] ?? m.status}</Badge>}
                    </div>
                    <code className="text-xs text-muted-foreground">{m.id}</code>
                    {m.notes && <p className="mt-1 max-w-md text-xs text-muted-foreground">{m.notes}</p>}
                  </TableCell>
                  <TableCell className="align-top">{m.max_reference_images}</TableCell>
                  <TableCell className="max-w-48 align-top text-xs whitespace-normal">{m.aspect_ratios.join(', ')}</TableCell>
                  <TableCell className="align-top whitespace-normal">
                    <div>{formatUsd(m.price_per_image_usd)}</div>
                    {m.price_note && <p className="max-w-xs text-xs text-muted-foreground">{m.price_note}</p>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
