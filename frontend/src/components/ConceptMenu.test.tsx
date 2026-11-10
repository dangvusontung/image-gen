import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it } from 'vitest'
import { OutfitSwitcher, useConceptChoices } from './ConceptMenu'

function Harness() {
  const [choices, setChoices] = useConceptChoices('outfit-test')
  return <OutfitSwitcher choices={choices} onChange={setChoices} />
}
afterEach(() => localStorage.clear())

it('defaults to bikini and bare feet and remembers a selected outfit and glasses', async () => {
  const user = userEvent.setup()
  const view = render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('bikini')
  expect(screen.getByLabelText('Đổi giày concept')).toHaveValue('barefoot')
  await user.selectOptions(screen.getByLabelText('Đổi trang phục concept'), 'satin_dress')
  await user.click(screen.getByRole('checkbox', { name: '+ Kính' }))
  view.unmount()
  render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('satin_dress')
  expect(screen.getByRole('checkbox', { name: '+ Kính' })).toBeChecked()
})

it('migrates the old per-concept defaults once and remembers an explicit per-concept choice', async () => {
  localStorage.setItem('concept-choices:outfit-test', JSON.stringify({ outfit: 'auto', footwear: 'auto' }))
  const view = render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('bikini')
  expect(screen.getByLabelText('Đổi giày concept')).toHaveValue('barefoot')
  await userEvent.selectOptions(screen.getByLabelText('Đổi trang phục concept'), 'auto')
  await userEvent.selectOptions(screen.getByLabelText('Đổi giày concept'), 'auto')
  view.unmount()
  render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('auto')
  expect(screen.getByLabelText('Đổi giày concept')).toHaveValue('auto')
})


it('preserves an existing fashion outfit instead of resetting it during migration', () => {
  localStorage.setItem('concept-choices:outfit-test', JSON.stringify({ outfit: 'satin_pyjamas', glasses: true }))
  render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('satin_pyjamas')
  expect(screen.getByRole('checkbox', { name: '+ Kính' })).toBeChecked()
})


it('selects and remembers the black lounge set without changing the default', async () => {
  const view = render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('bikini')
  await userEvent.selectOptions(screen.getByLabelText('Đổi trang phục concept'), 'black_white_lounge')
  view.unmount()
  render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('black_white_lounge')
  expect(screen.getByRole('option', { name: 'Crop tank + short đen viền trắng' })).toBeInTheDocument()
})


it('remembers the white strapless dress without changing scene, lighting or glasses', async () => {
  localStorage.setItem('concept-choices:outfit-test', JSON.stringify({ outfit: 'auto', scene: 'garden_cafe', lighting: 'golden', glasses: true }))
  const view = render(<Harness />)
  await userEvent.selectOptions(screen.getByLabelText('Đổi trang phục concept'), 'white_strapless_mini')
  view.unmount()
  render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('white_strapless_mini')
  expect(JSON.parse(localStorage.getItem('concept-choices:outfit-test') || '{}')).toMatchObject({ scene: 'garden_cafe', lighting: 'golden', glasses: true })
})


it('offers all four tank and pleated-mini looks and remembers the chosen style', async () => {
  const view = render(<Harness />)
  for (const label of ['Tank trắng + mini xếp ly xám', 'Tank đen + mini xếp ly kem', 'Tank xanh pastel + mini xếp ly trắng', 'Tank đỏ rượu + mini xếp ly taupe']) {
    expect(screen.getByRole('option', { name: label })).toBeInTheDocument()
  }
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('bikini')
  await userEvent.selectOptions(screen.getByLabelText('Đổi trang phục concept'), 'tank_pleated_classic')
  view.unmount()
  render(<Harness />)
  expect(screen.getByLabelText('Đổi trang phục concept')).toHaveValue('tank_pleated_classic')
})
