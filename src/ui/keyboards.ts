import { InlineKeyboardMarkup } from 'telegraf/types';
import { getProcessingTypeById, PHOTO_PROCESSING_TYPES } from '../prompts/photo';
import { PAYMENT_PACKAGES } from '../services/payments.service';
import { formatBerriesCount, formatBerriesCountNominative, getTranslation, Language } from '../i18n/translations';

export function getMainMenuKeyboard(lang: Language | null | undefined = 'en'): InlineKeyboardMarkup {
  const t = getTranslation(lang);
  return {
    inline_keyboard: [
      [{ text: t.uploadPhoto, callback_data: 'upload_photo' }],
      [{ text: t.buyBerries, callback_data: 'buy_generation' }],
      [{ text: t.wallet, callback_data: 'wallet' }],
      [{ text: t.freeBerries, callback_data: 'free_berries' }],
      [{ text: t.changeLanguage, callback_data: 'change_language' }],
    ],
  };
}

export function getProcessingTypesKeyboard(lang: Language | null | undefined = 'en'): InlineKeyboardMarkup {
  const t = getTranslation(lang);
  return {
    inline_keyboard: [
      [{ text: t.processingTypeMediumSize, callback_data: 'processing_type_MediumSize' }],
      [{ text: t.processingTypeBigSize, callback_data: 'processing_type_BigSize' }],
      [{ text: t.back, callback_data: 'main_menu' }],
    ],
  };
}

export function getProcessingOptionsKeyboard(lang: Language | null | undefined, typeId: string): InlineKeyboardMarkup {
  const t = getTranslation(lang);
  const type = getProcessingTypeById(typeId);
  const options = type?.options || [];
  const buttons = options.map((opt) => {
    // Get localized name based on option ID
    let localizedName: string;
    switch (opt.id) {
      // Old IDs (for backward compatibility)
      case 'A':
        localizedName = t.optionNakedBreasts;
        break;
      case 'B':
        localizedName = t.optionFullNaked;
        break;
      case 'C':
        localizedName = t.optionHappyNewYear;
        break;
      case 'SS_NB':
        localizedName = t.optionNakedBreasts;
        break;
      case 'BS_Bikini':
        localizedName = t.optionBikini;
        break;
      // MediumSize options
      case 'M_Ur':
        localizedName = t.optionUnderwear;
        break;
      case 'M_Bi':
        localizedName = t.optionBikini;
        break;
      case 'M_NK':
        localizedName = t.optionNakedBreasts;
        break;
      case 'M_FN':
        localizedName = t.optionFullNaked;
        break;
      case 'M_HNY':
        localizedName = t.optionHappyNewYear;
        break;
      case 'M_HNY18':
        localizedName = t.optionHappyNewYear;
        break;
      // BigSize options
      case 'B_Ur':
        localizedName = t.optionUnderwear;
        break;
      case 'B_Bi':
        localizedName = t.optionBikini;
        break;
      case 'B_NK':
        localizedName = t.optionNakedBreasts;
        break;
      case 'B_FN':
        localizedName = t.optionFullNaked;
        break;
      case 'B_HNY':
        localizedName = t.optionHappyNewYear;
        break;
      case 'B_HNY18':
        localizedName = t.optionHappyNewYear;
        break;
      default:
        localizedName = opt.name || opt.id; // Fallback
    }
    // Use emoji from photo.ts if available, otherwise use empty string
    const emoji = opt.emoji || '';
    const emojiPrefix = emoji ? `${emoji} ` : '';
    
    return [
      {
        text: `${emojiPrefix}${localizedName} | 🍓 ${formatBerriesCountNominative(lang, opt.berriesCost)}`,
        callback_data: `process_${opt.id}`,
      },
    ];
  });

  return {
    inline_keyboard: [
      ...buttons,
      [{ text: t.back, callback_data: 'processing_types' }],
    ],
  };
}

export function getPaymentPackagesKeyboard(lang: Language | null | undefined = 'en'): InlineKeyboardMarkup {
  const t = getTranslation(lang);
  const buttons: Array<Array<{ text: string; callback_data: string }>> = PAYMENT_PACKAGES.map((pkg) => {
    // Format: "🍓 1 berry | ⭐ 7 Stars" (Telegram Stars)
    // Localize the package title based on berries count (automatically localized for all languages)
    const localizedTitle = formatBerriesCount(lang, pkg.berries);

    // Just show berries count and stars, without "Buy" text
    return [{
      text: `🍓 ${localizedTitle} | ⭐ ${pkg.amountStars} ${t.stars}`,
      callback_data: `buy_${pkg.sku}`,
    }];
  });

  return {
    inline_keyboard: [
      ...buttons,
      [{ text: t.back, callback_data: 'buy_generation' }],
    ],
  };
}

export function getBackToMenuKeyboard(lang: Language | null | undefined = 'en'): InlineKeyboardMarkup {
  const t = getTranslation(lang);
  return {
    inline_keyboard: [[{ text: t.backToMenu, callback_data: 'main_menu' }]],
  };
}

export function getLanguageSelectionKeyboard(): InlineKeyboardMarkup {
  const t = getTranslation('en');
  return {
    inline_keyboard: [
      [{ text: '🇺🇸 English', callback_data: 'lang_en' }],
      [{ text: '🇮🇳 हिन्दी (Hindi)', callback_data: 'lang_hi' }],
      [{ text: '🇮🇩 Bahasa Indonesia', callback_data: 'lang_id' }],
      [{ text: '🇧🇷 Português (Brasil)', callback_data: 'lang_pt' }],
      [{ text: '🇷🇺 Русский', callback_data: 'lang_ru' }],
      // Back to menu
      [{ text: getTranslation('ru').backToMenu, callback_data: 'main_menu' }],
    ],
  };
}

export function getTermsAgreementKeyboard(lang: Language | null | undefined = 'en'): InlineKeyboardMarkup {
  const t = getTranslation(lang);
  return {
    inline_keyboard: [
      [{ text: t.iAgree, callback_data: 'terms_agree' }],
    ],
  };
}

export function getProceedPaymentKeyboard(lang: Language | null | undefined = 'en'): InlineKeyboardMarkup {
  const t = getTranslation(lang);
  return {
    inline_keyboard: [
      [{ text: t.proceedButton, callback_data: 'proceed_payment' }],
      [{ text: t.back, callback_data: 'payment_method_stars' }],
    ],
  };
}

export function getReferralKeyboard(lang: Language | null | undefined, referralLink: string): InlineKeyboardMarkup {
  const t = getTranslation(lang);
  return {
    inline_keyboard: [
      [{ text: t.shareButton, url: `https://t.me/share/url?url=${encodeURIComponent(referralLink)}&text=${encodeURIComponent(t.referralDescription)}` }],
      [{ text: t.backToMenu, callback_data: 'main_menu' }],
    ],
  };
}

export function getPaymentMethodKeyboard(lang: Language | null | undefined = 'en'): InlineKeyboardMarkup {
  const t = getTranslation(lang);
  return {
    inline_keyboard: [
      [{ text: t.paymentMethodTelegramStars, callback_data: 'payment_method_stars' }],
      [{ text: t.paymentMethodCrypto, callback_data: 'payment_method_crypto' }],
      [{ text: t.backToMenu, callback_data: 'main_menu' }],
    ],
  };
}

export function getCryptoPaymentKeyboard(
  lang: Language | null | undefined,
  invoiceUrl: string | null,
  invoiceId: string
): InlineKeyboardMarkup {
  const t = getTranslation(lang);
  const buttons: any[] = [];
  
  // Add Pay button if invoice URL is available
  if (invoiceUrl) {
    buttons.push([{ text: t.payButton, url: invoiceUrl }]);
  }
  
  buttons.push(
    [{ text: t.checkPaymentButton, callback_data: `check_crypto_payment_${invoiceId}` }]
  );
  
  return {
    inline_keyboard: buttons,
  };
}

