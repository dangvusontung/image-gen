import type { ConceptProposal } from '@/api/client'

const GROUPS = [
  {
    "name": "Phòng khách & sinh hoạt",
    "slots": [
      1,
      9,
      10,
      17,
      21,
      28,
      53,
      54,
      55,
      56,
      115,
      116,
      131,
      132,
      133,
      134,
      135,
      139,
      147,
      148,
      149,
      152,
      153,
      155,
      160,
      161,
      162,
      171,
      182,
      183,
      186,
      187
    ]
  },
  {
    "name": "Phòng ngủ & nghỉ ngơi",
    "slots": [
      2,
      5,
      11,
      15,
      16,
      18,
      19,
      20,
      24,
      25,
      41,
      42,
      43,
      44,
      93,
      94,
      95,
      97,
      98,
      107,
      108,
      127,
      128,
      130,
      138,
      145,
      146,
      150,
      151,
      156,
      159,
      163,
      167,
      168,
      169,
      172,
      173,
      174,
      175,
      176,
      178,
      180,
      184,
      185,
      190
    ]
  },
  {
    "name": "Bếp & bên cửa sổ",
    "slots": [
      12,
      13,
      14,
      27,
      81,
      82,
      83,
      84
    ]
  },
  {
    "name": "Phòng tắm",
    "slots": [
      22,
      45,
      46,
      47,
      48,
      105,
      106,
      144,
      96
    ]
  },
  {
    "name": "Làm đẹp & công việc",
    "slots": [
      7,
      23,
      73,
      74,
      75,
      76
    ]
  },
  {
    "name": "Café",
    "slots": [
      99,
      100,
      101,
      102,
      103,
      104,
      136,
      137
    ]
  },
  {
    "name": "Bể bơi",
    "slots": [
      4,
      29,
      30,
      31,
      32,
      33,
      34,
      35,
      36,
      37,
      38,
      39,
      40,
      122,
      123,
      124,
      125,
      126,
      158
    ]
  },
  {
    "name": "Biển",
    "slots": [
      49,
      50,
      51,
      52,
      129,
      164,
      166
    ]
  },
  {
    "name": "Ngoài trời & du lịch",
    "slots": [
      3,
      6,
      8,
      26,
      117,
      165
    ]
  },
  {
    "name": "Việt Nam",
    "slots": [
      85,
      86,
      87,
      88,
      89,
      90,
      91,
      92
    ]
  },
  {
    "name": "Thời trang & ánh đèn",
    "slots": [
      61,
      62,
      63,
      64,
      65,
      66,
      67,
      68,
      69,
      70,
      71,
      72,
      109,
      110,
      111,
      112,
      113,
      114,
      118,
      119,
      120,
      121
    ]
  },
  {
    "name": "Studio & chân dung",
    "slots": [
      57,
      58,
      59,
      60,
      77,
      78,
      79,
      80,
      154,
      157,
      170,
      177,
      179,
      181,
      188,
      189
    ]
  },
  {
    "name": "Yoga",
    "slots": [
      140,
      141,
      142,
      143
    ]
  }
]

export function groupConcepts(concepts: ConceptProposal[], mode: 'scene' | 'family' | 'collection' = 'scene'): { name: string; items: ConceptProposal[] }[] {
  if (mode === 'collection') {
    const sets = new Map<string, { name: string; items: ConceptProposal[] }>()
    for (const concept of concepts.filter(row => row.collection_id)) {
      const id = concept.collection_id!
      const group = sets.get(id) ?? { name: concept.collection_name || id, items: [] }
      group.items.push(concept)
      sets.set(id, group)
    }
    return [...sets.values()].sort((a, b) => a.name.localeCompare(b.name, 'vi'))
      .map(group => ({ ...group, items: group.items.sort((a, b) => (a.display_number ?? a.slot) - (b.display_number ?? b.slot)) }))
      .concat(groupConcepts(concepts.filter(row => !row.collection_id), 'scene'))
  }
  if (mode === 'family') {
    const families = new Map<string, ConceptProposal[]>()
    for (const concept of concepts) {
      const name = concept.family || (concept.run === 0 ? 'Chưa phân loại' : 'Concept đề xuất')
      families.set(name, [...(families.get(name) ?? []), concept])
    }
    return [...families].sort(([a], [b]) => a.localeCompare(b, 'vi'))
      .map(([name, items]) => ({ name, items: items.sort((a, b) => (a.display_number ?? a.slot) - (b.display_number ?? b.slot)) }))
  }
  const grouped = new Map<string, ConceptProposal[]>()
  for (const concept of concepts) {
    const name = concept.run === 0
      ? concept.group || GROUPS.find(group => group.slots.includes(concept.slot))?.name || 'Khác'
      : 'Concept đề xuất'
    const items = grouped.get(name) ?? []
    items.push(concept)
    grouped.set(name, items)
  }
  return [...new Set([...GROUPS.map(group => group.name), ...grouped.keys(), 'Khác', 'Concept đề xuất'])]
    .filter(name => grouped.has(name))
    .map(name => ({ name, items: grouped.get(name)!.sort((a, b) => {
      if (a.display_number != null && b.display_number != null) return a.display_number - b.display_number
      if (!a.family && !b.family) return 0
      return (a.family ?? '').localeCompare(b.family ?? '', 'vi') || a.slot - b.slot
    }) }))
}

/** Number the full picker before filtering, without changing catalog or storage IDs. */
export function conceptDisplayNumbers(concepts: ConceptProposal[]) {
  return new Map(groupConcepts(concepts).flatMap(group => group.items)
    .map((concept, index) => [concept.slot, concept.display_number ?? index + 1]))
}
