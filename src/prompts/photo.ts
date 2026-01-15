export interface PhotoProcessingOption {
  id: string;
  emoji: string;
  name: string;
  prompt: string;
  berriesCost: number; // how many berries will be charged for this option
}

export interface PhotoProcessingType {
  id: string; // top-level type id
  options: PhotoProcessingOption[];
}

/**
 * Two-level processing:
 * 1) User selects a type
 * 2) User selects a specific option (prompt)
 */
export const PHOTO_PROCESSING_TYPES: PhotoProcessingType[] = [
  // Type 1: MediumSize
  {
    id: 'MediumSize',
    options: [
      {
        id: 'M_Ur',
        emoji: '',
        name: 'Underwear',
        berriesCost: 1,
        prompt: 'No filters, no stylization. She in a sexy lace bra and lace panties. Her arms are fully bare. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
      {
        id: 'M_Bi',
        emoji: '',
        name: 'Bikini',
        berriesCost: 1,
        prompt: 'No filters, no stylization. She in a bikini. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
      {
        id: 'M_HNY',
        emoji: '',
        name: 'Happy New Year',
        berriesCost: 1,
        prompt: 'No filters, no stylization. She in a red one-piece swimsuit. On the head of Santa Claus hat. Santa Claus gloves on the hands. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
      {
        id: 'M_NK',
        emoji: '🔞',
        name: 'Naked breasts',
        berriesCost: 2,
        prompt: 'No filters, no stylization. She is without her top with fully naked breasts. Her delicate breasts have slight asymmetry and natural contours; the areolas are little with light pigmentation and the nipples are soft. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
      {
        id: 'M_FN',
        emoji: '🔞',
        name: 'Full naked',
        berriesCost: 2,
        prompt: 'No filters, no stylization. She is naked. The breasts have slight asymmetry and natural contours; the areolas are little with light pigmentation and the nipples are delicate. The external genitalia are anatomically normal, and there is a small amount of hair in the pubic area. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
      {
        id: 'M_HNY18',
        emoji: '🔞',
        name: 'Happy New Year',
        berriesCost: 2,
        prompt: 'No filters, no stylization. She is topless in lace panties red. On the head of Santa Claus hat. Santa Claus gloves on the hands. The breasts have slight asymmetry and natural contours; the areolas are little with light pigmentation and the nipples are soft. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
    ],
  },
  // Type 2: BigSize
  {
    id: 'BigSize',
    options: [
      {
        id: 'B_Ur',
        emoji: '',
        name: 'Underwear',
        berriesCost: 1,
        prompt: 'No filters, no stylization. She has breasts big size and she in a sexy lace bra and lace panties. Her arms are fully bare. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
      {
        id: 'B_Bi',
        emoji: '',
        name: 'Bikini',
        berriesCost: 1,
        prompt: 'No filters, no stylization. She in a bikini big size. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
      {
        id: 'B_HNY',
        emoji: '',
        name: 'Happy New Year',
        berriesCost: 1,
        prompt: 'No filters, no stylization. She has breasts big size and she in a red one-piece swimsuit. On the head of Santa Claus hat. Santa Claus gloves on the hands. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
      {
        id: 'B_NK',
        emoji: '🔞',
        name: 'Naked breasts',
        berriesCost: 2,
        prompt: 'No filters, no stylization. She is without her top with fully naked breasts. Her delicate big size breasts have slight asymmetry and natural contours; the areolas are little with light pigmentation and the nipples are soft. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
      {
        id: 'B_FN',
        emoji: '🔞',
        name: 'Full naked',
        berriesCost: 2,
        prompt: 'No filters, no stylization. She is naked. The big size breasts have slight asymmetry and natural contours; the areolas are little with light pigmentation and the nipples are delicate. The external genitalia are anatomically normal, and there is a small amount of hair in the pubic area. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
      {
        id: 'B_HNY18',
        emoji: '🔞',
        name: 'Happy New Year',
        berriesCost: 2,
        prompt: 'No filters, no stylization. She is topless in lace panties red. On the head of Santa Claus hat. Santa Claus gloves on the hands. The big size breasts have slight asymmetry and natural contours; the areolas are little with light pigmentation, and the nipples are soft. Use only the visible area; do not reconstruct or extend cropped body parts. Keep all other elements unchanged.',
      },
    ],
  },
];

// Backward-compatible flattened list of all options
export const PHOTO_PROCESSING_OPTIONS: PhotoProcessingOption[] = PHOTO_PROCESSING_TYPES.flatMap((t) => t.options);

export function getProcessingTypeById(id: string): PhotoProcessingType | undefined {
  return PHOTO_PROCESSING_TYPES.find((t) => t.id === id);
}

export function getProcessingOptionById(id: string): PhotoProcessingOption | undefined {
  for (const type of PHOTO_PROCESSING_TYPES) {
    const opt = type.options.find((o) => o.id === id);
    if (opt) return opt;
  }
  return undefined;
}

