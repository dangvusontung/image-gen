import { Fragment } from 'react'
import { StarIcon, ArrowLeftIcon, ExternalLinkIcon, PlugZapIcon, RefreshCwIcon, RotateCcwIcon } from 'lucide-react'
import { useFetchProviderModels, useProviders, useResetProviderModels, useSpend, useTestProvider, type ProviderInfo } from '@/api/client'
import { ErrorAlert } from '@/components/ErrorAlert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import PresetManager from '@/components/PresetManager'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatUsd, groupByGeneration, MODEL_STATUS_LABEL, providerStatus } from '@/lib/providers'
import { useFavouriteModels } from '@/lib/favourites'

const KEY_ENV: Record<string, string> = { gemini: 'GEMINI_API_KEY', bfl: 'BFL_API_KEY', modelark: 'ARK_API_KEY' }

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
            Chi phí job 24h (báo cáo + ước tính): ${spend.data.spent_24h_usd.toFixed(2)} · Giới hạn ứng dụng: {spend.data.limit_usd <= 0 ? 'Không giới hạn' : `$${spend.data.limit_usd.toFixed(2)} / 24h`}
          </Badge>
        )}
      </header>

      <div className="mb-6"><PresetManager /></div>

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
  const fetchModels = useFetchProviderModels()
  const resetModels = useResetProviderModels()
  const status = providerStatus(provider)
  const env = KEY_ENV[provider.name]
  const canFetch = Boolean(provider.catalogue_source) && provider.key_configured
  const busy = fetchModels.isPending || resetModels.isPending
  const fetchedAt = provider.catalogue_fetched_at ? new Date(provider.catalogue_fetched_at).toLocaleString('vi-VN') : null
  const generations = groupByGeneration(provider.models)
  const { toggle, isFavourite } = useFavouriteModels()

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
          {canFetch && (
            <Button variant="outline" size="sm" onClick={() => fetchModels.mutate(provider.name)} disabled={busy}>
              <RefreshCwIcon /> {fetchModels.isPending ? 'Đang lấy…' : 'Lấy danh sách model'}
            </Button>
          )}
          {canFetch && fetchedAt && (
            <Button variant="ghost" size="sm" onClick={() => resetModels.mutate(provider.name)} disabled={busy}>
              <RotateCcwIcon /> Đặt lại
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
        {canFetch && (
          <p className="text-sm text-muted-foreground">
            {fetchedAt
              ? `Danh sách model đã lấy từ ${provider.display_name} lúc ${fetchedAt} và được lưu lại; khởi động lại backend vẫn giữ.`
              : 'Đang dùng danh sách model mặc định của ứng dụng. Bấm “Lấy danh sách model” để lấy đúng model mà tài khoản của bạn có và lưu lại.'}
          </p>
        )}
        {fetchModels.data && (
          <p role="status" className="text-sm text-emerald-700">
            Đã lưu {fetchModels.data.models.length} model từ {fetchModels.data.source}.
          </p>
        )}
        {resetModels.isSuccess && <p role="status" className="text-sm text-muted-foreground">Đã đặt lại về danh sách mặc định.</p>}
        {fetchModels.error && <ErrorAlert title="Không lấy được danh sách model" error={fetchModels.error} />}
        {resetModels.error && <ErrorAlert title="Không đặt lại được danh sách model" error={resetModels.error} />}
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
              {generations.map(({ generation, models }) => (
                <Fragment key={generation.key}>
                  {generations.length > 1 && (
                    <TableRow className="bg-muted/50 hover:bg-muted/50">
                      <TableCell colSpan={4} className="py-2 text-xs font-semibold tracking-wide uppercase">
                        {generation.label}
                        <span className="ml-2 font-normal normal-case text-muted-foreground">
                          {models.length} model
                        </span>
                      </TableCell>
                    </TableRow>
                  )}
                  {models.map((m) => (
                    <TableRow key={m.id}>
                      <TableCell className="align-top whitespace-normal">
                        <div className="flex flex-wrap items-center gap-1.5 font-medium">
                          {m.display_name}
                          {m.default && <Badge variant="secondary">Mặc định</Badge>}
                          {m.status !== 'ga' && <Badge variant="outline">{MODEL_STATUS_LABEL[m.status] ?? m.status}</Badge>}
                        </div>
                        <code className="text-xs text-muted-foreground">{m.id}</code>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          className="ml-1 align-middle"
                          aria-label={`${isFavourite(provider.name, m.id) ? 'Bỏ yêu thích' : 'Đánh dấu yêu thích'} ${m.id}`}
                          aria-pressed={isFavourite(provider.name, m.id)}
                          onClick={() => toggle(provider.name, m.id)}
                        >
                          <StarIcon className={isFavourite(provider.name, m.id) ? 'fill-current text-amber-500' : ''} />
                        </Button>
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
                </Fragment>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
