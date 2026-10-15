import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it } from 'vitest'
import { OutfitSwitcher, useConceptChoices } from './ConceptMenu'

function Harness() {
  const [choices, setChoices] = useConceptChoices('outfit-test')
  return <OutfitSwitcher choices={choices} onChange={setChoices} />
}
afterEach(() => localStorage.clear())

it('defaults to bikini and remembers a selected outfit and glasses', async () => {
  const user = userEvent.setup()
  const view = render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('bikini')
  await user.selectOptions(screen.getByLabelText('Đổi trang phục concept'), 'satin_dress')
  await user.click(screen.getByRole('checkbox', { name: '+ Kính' }))
  view.unmount()
  render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('satin_dress')
  expect(screen.getByRole('checkbox', { name: '+ Kính' })).toBeChecked()
})

it('migrates an old auto default once while preserving a deliberate per-concept choice', async () => {
  localStorage.setItem('concept-choices:outfit-test', JSON.stringify({ outfit: 'auto' }))
  const view = render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('bikini')
  await userEvent.selectOptions(screen.getByLabelText('Đổi trang phục concept'), 'auto')
  view.unmount()
  render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('auto')
})
