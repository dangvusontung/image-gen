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
      155
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
      156
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
      129
    ]
  },
  {
    "name": "Ngoài trời & du lịch",
    "slots": [
      3,
      6,
      8,
      26,
      117
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
      157
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

export function groupConcepts(concepts: ConceptProposal[]) {
  const grouped = new Map<string, ConceptProposal[]>()
  for (const concept of concepts) {
    const name = concept.run === 0
      ? GROUPS.find(group => group.slots.includes(concept.slot))?.name ?? 'Khác'
      : 'Concept đề xuất'
    const items = grouped.get(name) ?? []
    items.push(concept)
    grouped.set(name, items)
  }
  return [...GROUPS.map(group => group.name), 'Khác', 'Concept đề xuất']
    .filter(name => grouped.has(name))
    .map(name => ({ name, items: grouped.get(name)! }))
}

/** Number the full picker before filtering, without changing catalog or storage IDs. */
export function conceptDisplayNumbers(concepts: ConceptProposal[]) {
  return new Map(groupConcepts(concepts).flatMap(group => group.items)
    .map((concept, index) => [concept.slot, index + 1]))
}
