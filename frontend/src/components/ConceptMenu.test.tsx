import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it } from 'vitest'
import { OutfitSwitcher, useConceptChoices } from './ConceptMenu'

function Harness() {
  const [choices, setChoices] = useConceptChoices('outfit-test')
  return <OutfitSwitcher choices={choices} onChange={setChoices} />
}
afterEach(() => localStorage.clear())

it('defaults to per-concept clothing and remembers a selected outfit and glasses', async () => {
  const user = userEvent.setup()
  const view = render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('auto')
  await user.selectOptions(screen.getByLabelText('Đổi trang phục concept'), 'satin_dress')
  await user.click(screen.getByRole('checkbox', { name: '+ Kính' }))
  view.unmount()
  render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('satin_dress')
  expect(screen.getByRole('checkbox', { name: '+ Kính' })).toBeChecked()
})

it('migrates the old bikini default once and still allows an explicit bikini selection', async () => {
  localStorage.setItem('concept-choices:outfit-test', JSON.stringify({ outfit: 'bikini' }))
  const view = render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('auto')
  await userEvent.selectOptions(screen.getByLabelText('Đổi trang phục concept'), 'bikini')
  view.unmount()
  render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('bikini')
})


it('preserves an existing fashion outfit instead of resetting it during migration', () => {
  localStorage.setItem('concept-choices:outfit-test', JSON.stringify({ outfit: 'satin_pyjamas', glasses: true }))
  render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('satin_pyjamas')
  expect(screen.getByRole('checkbox', { name: '+ Kính' })).toBeChecked()
})
