export type Language = 'en' | 'hi' | 'id' | 'pt' | 'ru';

export interface Translations {
  languageSelection: string;
  termsText: string;
  welcome: string;
  mainMenu: string;
  uploadPhoto: string;
  buyGeneration: string;
  wallet: string;
  changeLanguage: string;
  back: string;
  backToMenu: string;
  photoReceived: string;
  selectProcessing: string;
  processing: string;
  done: string;
  remains: string;
  noCredits: string;
  buyPackage: string;
  freeCredits: string;
  paidCredits: string;
  freeGenerations: string;
  paidGenerations: string;
  paymentSuccessful: string;
  creditsAdded: string;
  errorProcessingPhoto: string;
  errorReceivingPhoto: string;
  photoExpired: string;
  uploadNewPhoto: string;
  processingInProgress: string;
  pleaseWait: string;
  minorDetected: string;
  timeoutMessage: string;
  timeoutStillRunningMessage: string;
  fileUnavailable: string;
  serviceUnavailable: string;
  processingFailed: string;
  failedToStart: string;
  tryAgainLater: string;
  languageSet: string;
  termsAccepted: string;
  pleaseCompleteSetup: string;
  iAgree: string;
  uploadPhotoPrompt: string;
  optionNakedBreasts: string;
  optionFullNaked: string;
  optionHappyNewYear: string;
  optionBikini: string;
  optionUnderwear: string;
  processingTypeMediumSize: string;
  processingTypeBigSize: string;
  errorOccurred: string;
  noPhotoFound: string;
  invalidProcessingOption: string;
  processingOptionNotFound: string;
  photoExpiredOrNotFound: string;
  invalidPackage: string;
  packageNotFound: string;
  paymentInvalidData: string;
  paymentPackageNotFound: string;
  paymentAmountMismatch: string;
  paymentInvalidCurrency: string;
  paymentProcessingError: string;
  walletBerriesMessage: string;
  statsTitle: string;
  statsTotalStars: string;
  statsTotalUsers: string;
  statsTotalPayments: string;
  statsAvgCheck: string;
  queueWaiting: string;
  rateLimitError: string;
  stars: string;
  total: string;
  invoiceTitle: string;
  invoiceDescription: string;
  generation: string;
  berryNominative: string;
  berriesFew: string;
  generations: string;
  commandUploadDescription: string;
  commandBuyDescription: string;
  commandWalletDescription: string;
  commandInviteDescription: string;
  commandLanguageDescription: string;
  commandTermsDescription: string;
  commandPrivacyDescription: string;
  paymentAgreement: string;
  proceedButton: string;
  freeBerries: string;
  referralTitle: string;
  referralDescription: string;
  shareButton: string;
  referralRewardNotification: string;
  buyBerries: string;
  selectPaymentMethod: string;
  paymentMethodTelegramStars: string;
  paymentMethodCrypto: string;
  cryptoPaymentInstruction: string;
  cryptoPaymentDetails: string;
  cryptoPaymentTransactionId: string;
  cryptoPaymentAmount: string;
  cryptoPaymentBerries: string;
  cryptoPaymentWalletAddress: string;
  cryptoPaymentImportant: string;
  cryptoPaymentImportant1: string;
  cryptoPaymentImportant2: string;
  cryptoPaymentImportant3: string;
  payButton: string;
  checkPaymentButton: string;
  cancelButton: string;
  paymentNotConfirmed: string;
  paymentChecking: string;
  paymentSuccess: string;
  paymentFailed: string;
  paymentPartiallyPaid: string;
  paymentRateLimited: string;
  cryptoPaymentUnavailable: string;
  cryptoPaymentConversionError: string;
  cryptoPaymentMinimalAmountError: string;
}

const translations: Record<Language, Translations> = {
  en: {
    languageSelection: 'Language selection:',
    termsText: `By clicking the 'I Agree' button, the user confirms that they have read the [Privacy Policy](https://titsberry.github.io/privacy.html) and [Terms of Use](https://titsberry.github.io/terms.html), understand them, and accept them in full.`,
    welcome: '👋 Welcome! Use the menu below to upload photos for processing.',
    mainMenu: '📋 Main menu:',
    uploadPhoto: '📷 Upload a photo',
    buyGeneration: '💳 Buy',
    wallet: '📊 My Balance',
    changeLanguage: '🌐 Change the language',
    back: '⬅️ Back',
    backToMenu: '⬅️ Back to menu',
    photoReceived: 'The photo was received. Select breast size.',
    selectProcessing: 'Select processing.',
    processing: '⏳ Processing… Please wait 2–3 minutes.',
    done: '✅ Done.',
    remains: 'Berries left:',
    noCredits: '💳 You have no berries remaining. Please purchase a package:',
    buyPackage: 'Please purchase a berries package:',
    freeCredits: '🆓 Free berries:',
    paidCredits: '💳 Paid berries:',
    freeGenerations: '🆓 Free berries:',
    paidGenerations: '💳 Paid berries:',
    paymentSuccessful: '✅ Payment successful!',
    creditsAdded: 'added to your account.',
    errorProcessingPhoto: '❌ Error processing photo.',
    errorReceivingPhoto: '❌ Error receiving photo. Please try again.',
    photoExpired: '⏰ Photo expired. Please upload a new photo.',
    uploadNewPhoto: 'Please upload a new photo.',
    processingInProgress: 'Processing already in progress. Please wait.',
    pleaseWait: 'Please wait.',
    minorDetected: '⚠️ Image could not be processed\n\nAs a result of an automated safety check, the image was identified as potentially containing signs of a minor, therefore processing is not available.\n\nPlease choose a different image and try again.',
    timeoutMessage: 'Processing is taking longer than expected. The task may still be running. Please try again later or check back in a few minutes.',
    timeoutStillRunningMessage: '⏳ High service load: processing will take longer.\n\nWe are processing many requests simultaneously, so your task is still running. The photo will be sent immediately after processing is complete. Thank you for your patience!',
    fileUnavailable: 'The uploaded file is unavailable. Please try uploading the photo again.',
    serviceUnavailable: 'TitsBerry service is temporarily unavailable (server error). Please try again in a few moments.',
    processingFailed: 'Processing failed. Please try again.',
    failedToStart: 'Failed to start processing. Please check your photo and try again.',
    tryAgainLater: 'Please try again later.',
    languageSet: 'Language set to',
    termsAccepted: 'Terms accepted',
    pleaseCompleteSetup: 'Please complete setup first',
    iAgree: 'I Agree',
    uploadPhotoPrompt: '📷 Send a photo for processing.\n⚠️ We do not save your photos — the image is used only for processing and then automatically deleted.',
    optionNakedBreasts: 'Naked breasts',
    optionFullNaked: 'Full naked',
    optionHappyNewYear: 'Happy New Year',
    optionBikini: 'Bikini',
    optionUnderwear: 'Underwear',
    processingTypeMediumSize: 'Medium size',
    processingTypeBigSize: 'Big size',
    errorOccurred: '❌ An error occurred. Please try again later.',
    noPhotoFound: '❌ No photo found in message.',
    invalidProcessingOption: 'Invalid processing option',
    processingOptionNotFound: 'Processing option not found',
    photoExpiredOrNotFound: 'Photo expired or not found. Please upload again.',
    invalidPackage: 'Invalid package',
    packageNotFound: 'Package not found',
    paymentInvalidData: 'Invalid payment data. Please try again.',
    paymentPackageNotFound: 'Payment package not found. Please try again.',
    paymentAmountMismatch: 'Payment amount mismatch. Please try again.',
    paymentInvalidCurrency: 'Invalid payment currency. Please use Telegram Stars.',
    paymentProcessingError: 'An error occurred while processing your payment. Please try again.',
    walletBerriesMessage: 'You have juicy berries left: 🍒 {count}. Enjoy.',
    statsTitle: '📊 Stats:',
    statsTotalStars: '⭐ Stars received:',
    statsTotalUsers: '👥 Total users:',
    statsTotalPayments: '🧾 Payments:',
    statsAvgCheck: '📈 Average check:',
    queueWaiting: '⏳ Your request is in queue. Please wait...',
    rateLimitError: '⚠️ Too many requests. Please wait a moment and try again.',
    stars: 'Stars',
    total: 'Total berries:',
    invoiceTitle: 'Berries',
    invoiceDescription: 'berries for photo processing',
    generation: 'berry',
    berryNominative: 'berry',
    berriesFew: 'berries',
    generations: 'berries',
    commandUploadDescription: 'Upload a photo for processing',
    commandBuyDescription: 'Buy berries',
    commandWalletDescription: 'Check your berry balance',
    commandInviteDescription: 'Get free berries',
    commandLanguageDescription: 'Change the language',
    commandTermsDescription: 'View terms of service',
    commandPrivacyDescription: 'View privacy policy',
    paymentAgreement: 'By proceeding, you agree to the [Terms of Service](https://titsberry.github.io/terms.html) and [Privacy Policy](https://titsberry.github.io/privacy.html).',
    proceedButton: 'Proceed ➡️',
    freeBerries: '🍓 Free berries',
    referralTitle: '💌 Share your link with friends.\n🎁 For each new friend who follows your link and generates a photo, you will receive 🍓 1 berry.',
    referralDescription: '🎁 Catch the link — you can make your first generation for free.',
    shareButton: '📤 Share',
    referralRewardNotification: '🎉 Great news! Your friend activated the referral link and generated their first photo 😎.\n🍓 1 berry has been credited to your wallet.',
    buyBerries: '💳 Buy berries',
    selectPaymentMethod: 'Select payment method:',
    paymentMethodTelegramStars: '⭐ Telegram Stars',
    paymentMethodCrypto: '💎 Crypto',
    cryptoPaymentInstruction: 'Open the payment link, complete the payment, then click "Check payment".',
    cryptoPaymentDetails: '🧾 Payment Details:',
    cryptoPaymentTransactionId: '🆔 Transaction ID:',
    cryptoPaymentAmount: '💰 Amount:',
    cryptoPaymentBerries: '🍓 Will be credited:',
    cryptoPaymentWalletAddress: '🏦 Wallet Address:',
    cryptoPaymentImportant: 'ℹ️ Important:',
    cryptoPaymentImportant1: '🔹 Transfer exactly the specified amount;',
    cryptoPaymentImportant2: '🔹 After payment, click "Check payment";',
    cryptoPaymentImportant3: '🔹 Wait for 🍓 to be credited to your balance.',
    payButton: '💳 Pay',
    checkPaymentButton: '✅ Check payment',
    cancelButton: '❌ Cancel',
    paymentNotConfirmed: 'Payment is not yet confirmed. Please try again in a minute.',
    paymentChecking: 'Checking payment status...',
    paymentSuccess: 'Payment confirmed! Berries have been added to your wallet.',
    paymentFailed: 'Payment failed or expired. Please try again.',
    paymentPartiallyPaid: 'Payment is partially paid. Please complete the full payment amount.',
    paymentRateLimited: 'Please wait before checking again.',
    cryptoPaymentUnavailable: '⚠️ TON is temporarily unavailable in NOWPayments. Please try again later or use Telegram Stars for payment.',
    cryptoPaymentConversionError: '⚠️ Currency conversion error in NOWPayments. Please try again later or use Telegram Stars for payment.',
    cryptoPaymentMinimalAmountError: '⚠️ The payment amount is too small. Minimum amount for TON is higher. Please choose a package with more berries or use Telegram Stars for payment.',
  },
  hi: {
    languageSelection: 'भाषा चयन:',
    termsText: `'मैं सहमत हूं' बटन पर क्लिक करके, उपयोगकर्ता पुष्टि करता है कि उसने [गोपनीयता नीति](https://titsberry.github.io/privacy.html) और [उपयोग की शर्तें](https://titsberry.github.io/terms.html) पढ़ ली हैं, उन्हें समझता है और पूरी तरह से स्वीकार करता है।`,
    welcome: '👋 स्वागत है! फोटो प्रसंस्करण के लिए अपलोड करने के लिए नीचे मेनू का उपयोग करें।',
    mainMenu: '📋 मुख्य मेनू:',
    uploadPhoto: '📷 एक फोटो अपलोड करें',
    buyGeneration: '💳 खरीदें',
    wallet: '📊 मेरा बैलेंस',
    changeLanguage: '🌐 भाषा बदलें',
    back: '⬅️ वापस',
    backToMenu: '⬅️ मेनू पर वापस',
    photoReceived: 'फोटो प्राप्त हुई। स्तन का आकार चुनें।',
    selectProcessing: 'प्रसंस्करण चुनें।',
    processing: '⏳ प्रसंस्करण हो रहा है… कृपया 2–3 मिनट प्रतीक्षा करें।',
    done: '✅ हो गया।',
    remains: 'बाकी बेरी:',
    noCredits: '💳 आपके पास कोई बेरी शेष नहीं है। कृपया एक पैकेज खरीदें:',
    buyPackage: 'कृपया एक बेरी पैकेज खरीदें:',
    freeCredits: '🆓 मुफ्त बेरी:',
    paidCredits: '💳 भुगतान की गई बेरी:',
    freeGenerations: '🆓 मुफ्त बेरी:',
    paidGenerations: '💳 भुगतान की गई बेरी:',
    paymentSuccessful: '✅ भुगतान सफल!',
    creditsAdded: 'आपके खाते में जोड़ दी गईं।',
    errorProcessingPhoto: '❌ फोटो प्रसंस्करण में त्रुटि।',
    errorReceivingPhoto: '❌ फोटो प्राप्त करने में त्रुटि। कृपया पुनः प्रयास करें।',
    photoExpired: '⏰ फोटो समाप्त हो गई। कृपया एक नई फोटो अपलोड करें।',
    uploadNewPhoto: 'कृपया एक नई फोटो अपलोड करें।',
    processingInProgress: 'प्रसंस्करण पहले से चल रहा है। कृपया प्रतीक्षा करें।',
    pleaseWait: 'कृपया प्रतीक्षा करें।',
    minorDetected: '⚠️ छवि को प्रसंस्कृत नहीं किया जा सका\n\nएक स्वचालित सुरक्षा जांच के परिणामस्वरूप, छवि को संभावित रूप से एक नाबालिग के संकेतों वाली पहचान की गई थी, इसलिए प्रसंस्करण उपलब्ध नहीं है।\n\nकृपया एक अलग छवि चुनें और पुनः प्रयास करें।',
    timeoutMessage: 'प्रसंस्करण अपेक्षा से अधिक समय ले रहा है। कार्य अभी भी चल रहा हो सकता है। कृपया बाद में पुनः प्रयास करें या कुछ मिनटों में वापस जांचें।',
    timeoutStillRunningMessage: '⏳ सेवा पर उच्च भार: प्रसंस्करण में अधिक समय लगेगा।\n\nहम एक साथ कई अनुरोधों को संसाधित कर रहे हैं, इसलिए आपका कार्य अभी भी चल रहा है। प्रसंस्करण पूरा होने के तुरंत बाद फोटो भेज दी जाएगी। आपके धैर्य के लिए धन्यवाद!',
    fileUnavailable: 'अपलोड की गई फ़ाइल उपलब्ध नहीं है। कृपया फोटो को फिर से अपलोड करने का प्रयास करें।',
    serviceUnavailable: 'TitsBerry सेवा अस्थायी रूप से अनुपलब्ध है (सर्वर त्रुटि)। कृपया कुछ क्षणों में पुनः प्रयास करें।',
    processingFailed: 'प्रसंस्करण विफल रहा। कृपया पुनः प्रयास करें।',
    failedToStart: 'प्रसंस्करण शुरू करने में विफल। कृपया अपनी फोटो जांचें और पुनः प्रयास करें।',
    tryAgainLater: 'कृपया बाद में पुनः प्रयास करें।',
    languageSet: 'भाषा सेट की गई',
    termsAccepted: 'शर्तें स्वीकार की गईं',
    pleaseCompleteSetup: 'कृपया पहले सेटअप पूरा करें',
    iAgree: 'मैं सहमत हूं',
    uploadPhotoPrompt: '📷 प्रसंस्करण के लिए एक फोटो भेजें।\n⚠️ हम आपकी तस्वीरें सहेजते नहीं हैं — छवि का उपयोग केवल प्रसंस्करण के लिए किया जाता है और फिर स्वचालित रूप से हटा दी जाती है।',
    optionNakedBreasts: 'नग्न स्तन',
    optionFullNaked: 'पूर्ण नग्न',
    optionHappyNewYear: 'नया साल मुबारक',
    optionBikini: 'बिकिनी',
    optionUnderwear: 'अंडरवियर',
    processingTypeMediumSize: 'मध्यम आकार',
    processingTypeBigSize: 'बड़ा आकार',
    errorOccurred: '❌ एक त्रुटि हुई। कृपया बाद में पुनः प्रयास करें।',
    noPhotoFound: '❌ संदेश में कोई फोटो नहीं मिली।',
    invalidProcessingOption: 'अमान्य प्रसंस्करण विकल्प',
    processingOptionNotFound: 'प्रसंस्करण विकल्प नहीं मिला',
    photoExpiredOrNotFound: 'फोटो समाप्त हो गई या नहीं मिली। कृपया फिर से अपलोड करें।',
    invalidPackage: 'अमान्य पैकेज',
    packageNotFound: 'पैकेज नहीं मिला',
    paymentInvalidData: 'अमान्य भुगतान डेटा। कृपया पुनः प्रयास करें।',
    paymentPackageNotFound: 'भुगतान पैकेज नहीं मिला। कृपया पुनः प्रयास करें।',
    paymentAmountMismatch: 'भुगतान राशि मेल नहीं खाती। कृपया पुनः प्रयास करें।',
    paymentInvalidCurrency: 'अमान्य भुगतान मुद्रा। कृपया Telegram Stars का उपयोग करें।',
    paymentProcessingError: 'भुगतान संसाधित करते समय त्रुटि हुई। कृपया पुनः प्रयास करें।',
    walletBerriesMessage: 'आपके पास रसदार बेरी बची हैं: 🍒 {count}. आनंद लें।',
    statsTitle: '📊 आँकड़े:',
    statsTotalStars: '⭐ प्राप्त Stars:',
    statsTotalUsers: '👥 कुल उपयोगकर्ता:',
    statsTotalPayments: '🧾 भुगतान:',
    statsAvgCheck: '📈 औसत चेक:',
    queueWaiting: '⏳ आपका अनुरोध कतार में है। कृपया प्रतीक्षा करें...',
    rateLimitError: '⚠️ बहुत सारे अनुरोध। कृपया एक क्षण प्रतीक्षा करें और पुनः प्रयास करें।',
    stars: 'स्टार्स',
    total: 'कुल बेरी:',
    invoiceTitle: 'बेरी',
    invoiceDescription: 'फोटो प्रोसेसिंग के लिए बेरी',
    generation: 'बेरी',
    berryNominative: 'बेरी',
    berriesFew: 'बेरी',
    generations: 'बेरी',
    commandUploadDescription: 'प्रसंस्करण के लिए एक फोटो अपलोड करें',
    commandBuyDescription: 'बेरी खरीदें',
    commandWalletDescription: 'अपना बेरी बैलेंस जांचें',
    commandInviteDescription: 'मुफ्त बेरी प्राप्त करें',
    commandLanguageDescription: 'भाषा बदलें',
    commandTermsDescription: 'सेवा की शर्तें देखें',
    commandPrivacyDescription: 'गोपनीयता नीति देखें',
    paymentAgreement: 'आगे बढ़कर, आप [उपयोग की शर्तें](https://titsberry.github.io/terms.html) और [गोपनीयता नीति](https://titsberry.github.io/privacy.html) से सहमत हैं।',
    proceedButton: 'आगे बढ़ें ➡️',
    freeBerries: '🍓 मुफ्त जामुन',
    referralTitle: '💌 अपने दोस्तों के साथ अपना लिंक साझा करें।\n🎁 प्रत्येक नए दोस्त के लिए जो आपके लिंक का अनुसरण करता है और एक फोटो जनरेट करता है, आपको 🍓 1 जामुन मिलेगा।',
    referralDescription: '🎁 लिंक पकड़ें — आप अपनी पहली जनरेशन मुफ्त में कर सकते हैं।',
    shareButton: '📤 साझा करें',
    referralRewardNotification: '🎉 बढ़िया खबर! आपके दोस्त ने रेफरल लिंक सक्रिय किया और अपनी पहली फोटो जनरेट की 😎।\n🍓 1 जामुन आपके वॉलेट में जमा किया गया है।',
    buyBerries: '💳 जामुन खरीदें',
    selectPaymentMethod: 'भुगतान विधि चुनें:',
    paymentMethodTelegramStars: '⭐ टेलीग्राम स्टार्स',
    paymentMethodCrypto: '💎 क्रिप्टो',
    cryptoPaymentInstruction: 'भुगतान लिंक खोलें, भुगतान पूरा करें, फिर "भुगतान जांचें" पर क्लिक करें।',
    cryptoPaymentDetails: '🧾 भुगतान विवरण:',
    cryptoPaymentTransactionId: '🆔 लेनदेन ID:',
    cryptoPaymentAmount: '💰 राशि:',
    cryptoPaymentBerries: '🍓 जमा होगा:',
    cryptoPaymentWalletAddress: '🏦 वॉलेट पता:',
    cryptoPaymentImportant: 'ℹ️ महत्वपूर्ण:',
    cryptoPaymentImportant1: '🔹 बिल्कुल निर्दिष्ट राशि स्थानांतरित करें;',
    cryptoPaymentImportant2: '🔹 भुगतान के बाद "भुगतान जांचें" पर क्लिक करें;',
    cryptoPaymentImportant3: '🔹 अपने बैलेंस में 🍓 जमा होने की प्रतीक्षा करें।',
    payButton: '💳 भुगतान करें',
    checkPaymentButton: '✅ भुगतान जांचें',
    cancelButton: '❌ रद्द करें',
    paymentNotConfirmed: 'भुगतान अभी तक पुष्टि नहीं हुई है। कृपया एक मिनट बाद पुनः प्रयास करें।',
    paymentChecking: 'भुगतान स्थिति जांच रहा है...',
    paymentSuccess: 'भुगतान पुष्टि हो गई! जामुन आपके वॉलेट में जोड़ दिए गए हैं।',
    paymentFailed: 'भुगतान विफल या समाप्त हो गई। कृपया पुनः प्रयास करें।',
    paymentPartiallyPaid: 'भुगतान आंशिक रूप से किया गया है। कृपया पूरी राशि का भुगतान करें।',
    paymentRateLimited: 'कृपया फिर से जांचने से पहले प्रतीक्षा करें।',
    cryptoPaymentUnavailable: '⚠️ TON अभी NOWPayments में अस्थायी रूप से उपलब्ध नहीं है। कृपया बाद में पुनः प्रयास करें या भुगतान के लिए Telegram Stars का उपयोग करें।',
    cryptoPaymentConversionError: '⚠️ NOWPayments में मुद्रा रूपांतरण त्रुटि। कृपया बाद में पुनः प्रयास करें या भुगतान के लिए Telegram Stars का उपयोग करें।',
    cryptoPaymentMinimalAmountError: '⚠️ भुगतान राशि बहुत छोटी है। TON के लिए न्यूनतम राशि अधिक है। कृपया अधिक जामुन वाला पैकेज चुनें या भुगतान के लिए Telegram Stars का उपयोग करें।',
  },
  id: {
    languageSelection: 'Pemilihan bahasa:',
    termsText: `Dengan menekan tombol 'Saya Setuju', pengguna menyatakan bahwa mereka telah membaca [Kebijakan Privasi](https://titsberry.github.io/privacy.html) dan [Ketentuan Penggunaan](https://titsberry.github.io/terms.html), memahaminya, dan menyetujuinya sepenuhnya.`,
    welcome: '👋 Selamat datang! Gunakan menu di bawah untuk mengunggah foto untuk diproses.',
    mainMenu: '📋 Menu utama:',
    uploadPhoto: '📷 Unggah foto',
    buyGeneration: '💳 Beli',
    wallet: '📊 Saldo Saya',
    changeLanguage: '🌐 Ubah bahasa',
    back: '⬅️ Kembali',
    backToMenu: '⬅️ Kembali ke menu',
    photoReceived: 'Foto telah diterima. Pilih ukuran payudara.',
    selectProcessing: 'Pilih pemrosesan.',
    processing: '⏳ Memproses… Silakan tunggu 2–3 menit.',
    done: '✅ Selesai.',
    remains: 'Sisa berry:',
    noCredits: '💳 Anda tidak memiliki berry tersisa. Silakan beli paket:',
    buyPackage: 'Silakan beli paket berry:',
    freeCredits: '🆓 Berry gratis:',
    paidCredits: '💳 Berry berbayar:',
    freeGenerations: '🆓 Berry gratis:',
    paidGenerations: '💳 Berry berbayar:',
    paymentSuccessful: '✅ Pembayaran berhasil!',
    creditsAdded: 'ditambahkan ke akun Anda.',
    errorProcessingPhoto: '❌ Kesalahan memproses foto.',
    errorReceivingPhoto: '❌ Kesalahan menerima foto. Silakan coba lagi.',
    photoExpired: '⏰ Foto kedaluwarsa. Silakan unggah foto baru.',
    uploadNewPhoto: 'Silakan unggah foto baru.',
    processingInProgress: 'Pemrosesan sedang berlangsung. Silakan tunggu.',
    pleaseWait: 'Silakan tunggu.',
    minorDetected: '⚠️ Gambar tidak dapat diproses\n\nSebagai hasil dari pemeriksaan keamanan otomatis, gambar diidentifikasi berpotensi mengandung tanda-tanda minor, oleh karena itu pemrosesan tidak tersedia.\n\nSilakan pilih gambar yang berbeda dan coba lagi.',
    timeoutMessage: 'Pemrosesan memakan waktu lebih lama dari yang diharapkan. Tugas mungkin masih berjalan. Silakan coba lagi nanti atau periksa kembali dalam beberapa menit.',
    timeoutStillRunningMessage: '⏳ Beban layanan tinggi: pemrosesan akan memakan waktu lebih lama.\n\nKami sedang memproses banyak permintaan secara bersamaan, jadi tugas Anda masih berjalan. Foto akan dikirim segera setelah pemrosesan selesai. Terima kasih atas kesabaran Anda!',
    fileUnavailable: 'File yang diunggah tidak tersedia. Silakan coba mengunggah foto lagi.',
    serviceUnavailable: 'Layanan TitsBerry sementara tidak tersedia (kesalahan server). Silakan coba lagi dalam beberapa saat.',
    processingFailed: 'Pemrosesan gagal. Silakan coba lagi.',
    failedToStart: 'Gagal memulai pemrosesan. Silakan periksa foto Anda dan coba lagi.',
    tryAgainLater: 'Silakan coba lagi nanti.',
    languageSet: 'Bahasa diatur ke',
    termsAccepted: 'Ketentuan diterima',
    pleaseCompleteSetup: 'Silakan selesaikan pengaturan terlebih dahulu',
    iAgree: 'Saya Setuju',
    uploadPhotoPrompt: '📷 Kirim foto untuk diproses.\n⚠️ Kami tidak menyimpan foto Anda — gambar hanya digunakan untuk pemrosesan dan kemudian otomatis dihapus.',
    optionNakedBreasts: 'Payudara telanjang',
    optionFullNaked: 'Telanjang penuh',
    optionHappyNewYear: 'Selamat Tahun Baru',
    optionBikini: 'Bikini',
    optionUnderwear: 'Pakaian dalam',
    processingTypeMediumSize: 'Ukuran sedang',
    processingTypeBigSize: 'Ukuran besar',
    errorOccurred: '❌ Terjadi kesalahan. Silakan coba lagi nanti.',
    noPhotoFound: '❌ Tidak ada foto ditemukan dalam pesan.',
    invalidProcessingOption: 'Opsi pemrosesan tidak valid',
    processingOptionNotFound: 'Opsi pemrosesan tidak ditemukan',
    photoExpiredOrNotFound: 'Foto kedaluwarsa atau tidak ditemukan. Silakan unggah lagi.',
    invalidPackage: 'Paket tidak valid',
    packageNotFound: 'Paket tidak ditemukan',
    paymentInvalidData: 'Data pembayaran tidak valid. Silakan coba lagi.',
    paymentPackageNotFound: 'Paket pembayaran tidak ditemukan. Silakan coba lagi.',
    paymentAmountMismatch: 'Jumlah pembayaran tidak sesuai. Silakan coba lagi.',
    paymentInvalidCurrency: 'Mata uang pembayaran tidak valid. Silakan gunakan Telegram Stars.',
    paymentProcessingError: 'Terjadi kesalahan saat memproses pembayaran Anda. Silakan coba lagi.',
    walletBerriesMessage: 'Berry lezat tersisa: 🍒 {count}. Nikmati.',
    statsTitle: '📊 Statistik:',
    statsTotalStars: '⭐ Stars diterima:',
    statsTotalUsers: '👥 Total pengguna:',
    statsTotalPayments: '🧾 Pembayaran:',
    statsAvgCheck: '📈 Rata-rata pembelian:',
    queueWaiting: '⏳ Permintaan Anda sedang dalam antrian. Silakan tunggu...',
    rateLimitError: '⚠️ Terlalu banyak permintaan. Silakan tunggu sebentar dan coba lagi.',
    stars: 'Bintang',
    total: 'Total berry:',
    invoiceTitle: 'Berry',
    invoiceDescription: 'berry untuk pemrosesan foto',
    generation: 'berry',
    berryNominative: 'berry',
    berriesFew: 'berry',
    generations: 'berry',
    commandUploadDescription: 'Unggah foto untuk diproses',
    commandBuyDescription: 'Beli berry',
    commandWalletDescription: 'Periksa saldo berry Anda',
    commandInviteDescription: 'Dapatkan berry gratis',
    commandLanguageDescription: 'Ubah bahasa',
    commandTermsDescription: 'Lihat syarat layanan',
    commandPrivacyDescription: 'Lihat kebijakan privasi',
    paymentAgreement: 'Dengan melanjutkan, Anda menyetujui [Ketentuan Layanan](https://titsberry.github.io/terms.html) dan [Kebijakan Privasi](https://titsberry.github.io/privacy.html).',
    proceedButton: 'Lanjutkan ➡️',
    freeBerries: '🍓 Beri gratis',
    referralTitle: '💌 Bagikan tautan Anda dengan teman.\n🎁 Untuk setiap teman baru yang mengikuti tautan Anda dan menghasilkan foto, Anda akan menerima 🍓 1 beri.',
    referralDescription: '🎁 Ambil tautannya — Anda bisa membuat generasi pertama secara gratis.',
    shareButton: '📤 Bagikan',
    referralRewardNotification: '🎉 Berita bagus! Teman Anda mengaktifkan tautan referral dan menghasilkan foto pertama mereka 😎.\n🍓 1 beri telah dikreditkan ke dompet Anda.',
    buyBerries: '💳 Beli beri',
    selectPaymentMethod: 'Pilih metode pembayaran:',
    paymentMethodTelegramStars: '⭐ Telegram Stars',
    paymentMethodCrypto: '💎 Crypto',
    cryptoPaymentInstruction: 'Buka tautan pembayaran, selesaikan pembayaran, lalu klik "Periksa pembayaran".',
    cryptoPaymentDetails: '🧾 Detail Pembayaran:',
    cryptoPaymentTransactionId: '🆔 ID Transaksi:',
    cryptoPaymentAmount: '💰 Jumlah:',
    cryptoPaymentBerries: '🍓 Akan dikreditkan:',
    cryptoPaymentWalletAddress: '🏦 Alamat Wallet:',
    cryptoPaymentImportant: 'ℹ️ Penting:',
    cryptoPaymentImportant1: '🔹 Transfer tepat jumlah yang ditentukan;',
    cryptoPaymentImportant2: '🔹 Setelah pembayaran, klik "Periksa pembayaran";',
    cryptoPaymentImportant3: '🔹 Tunggu 🍓 dikreditkan ke saldo Anda.',
    payButton: '💳 Bayar',
    checkPaymentButton: '✅ Periksa pembayaran',
    cancelButton: '❌ Batal',
    paymentNotConfirmed: 'Pembayaran belum dikonfirmasi. Silakan coba lagi dalam satu menit.',
    paymentChecking: 'Memeriksa status pembayaran...',
    paymentSuccess: 'Pembayaran dikonfirmasi! Beri telah ditambahkan ke dompet Anda.',
    paymentFailed: 'Pembayaran gagal atau kedaluwarsa. Silakan coba lagi.',
    paymentPartiallyPaid: 'Pembayaran sebagian dibayar. Silakan selesaikan pembayaran penuh.',
    paymentRateLimited: 'Harap tunggu sebelum memeriksa lagi.',
    cryptoPaymentUnavailable: '⚠️ TON sementara tidak tersedia di NOWPayments. Silakan coba lagi nanti atau gunakan Telegram Stars untuk pembayaran.',
    cryptoPaymentConversionError: '⚠️ Kesalahan konversi mata uang di NOWPayments. Silakan coba lagi nanti atau gunakan Telegram Stars untuk pembayaran.',
    cryptoPaymentMinimalAmountError: '⚠️ Jumlah pembayaran terlalu kecil. Jumlah minimum untuk TON lebih tinggi. Silakan pilih paket dengan lebih banyak berry atau gunakan Telegram Stars untuk pembayaran.',
  },
  pt: {
    languageSelection: 'Seleção de idioma:',
    termsText: `Ao clicar no botão 'Eu Concordo', o usuário confirma que leu a [Política de Privacidade](https://titsberry.github.io/privacy.html) e os [Termos de Uso](https://titsberry.github.io/terms.html), os compreende e os aceita integralmente.`,
    welcome: '👋 Bem-vindo! Use o menu abaixo para enviar fotos para processamento.',
    mainMenu: '📋 Menu principal:',
    uploadPhoto: '📷 Enviar uma foto',
    buyGeneration: '💳 Comprar',
    wallet: '📊 Meu Saldo',
    changeLanguage: '🌐 Alterar idioma',
    back: '⬅️ Voltar',
    backToMenu: '⬅️ Voltar ao menu',
    photoReceived: 'A foto foi recebida. Selecione o tamanho do seio.',
    selectProcessing: 'Selecione o processamento.',
    processing: '⏳ Processando… Aguarde de 2 a 3 minutos.',
    done: '✅ Concluído.',
    remains: 'Bagas restantes:',
    noCredits: '💳 Você não tem bagas restantes. Por favor, compre um pacote:',
    buyPackage: 'Por favor, compre um pacote de bagas:',
    freeCredits: '🆓 Bagas grátis:',
    paidCredits: '💳 Bagas pagas:',
    freeGenerations: '🆓 Bagas grátis:',
    paidGenerations: '💳 Bagas pagas:',
    paymentSuccessful: '✅ Pagamento bem-sucedido!',
    creditsAdded: 'adicionada(s) à sua conta.',
    errorProcessingPhoto: '❌ Erro ao processar foto.',
    errorReceivingPhoto: '❌ Erro ao receber foto. Por favor, tente novamente.',
    photoExpired: '⏰ Foto expirada. Por favor, envie uma nova foto.',
    uploadNewPhoto: 'Por favor, envie uma nova foto.',
    processingInProgress: 'Processamento já em andamento. Por favor, aguarde.',
    pleaseWait: 'Por favor, aguarde.',
    minorDetected: '⚠️ A imagem não pôde ser processada\n\nComo resultado de uma verificação automática de segurança, a imagem foi identificada como potencialmente contendo sinais de menor, portanto o processamento não está disponível.\n\nPor favor, escolha uma imagem diferente e tente novamente.',
    timeoutMessage: 'O processamento está levando mais tempo do que o esperado. A tarefa ainda pode estar em execução. Por favor, tente novamente mais tarde ou verifique novamente em alguns minutos.',
    timeoutStillRunningMessage: '⏳ Alta carga no serviço: o processamento levará mais tempo.\n\nEstamos processando muitas solicitações simultaneamente, então sua tarefa ainda está em andamento. A foto será enviada imediatamente após a conclusão do processamento. Obrigado pela sua paciência!',
    fileUnavailable: 'O arquivo enviado não está disponível. Por favor, tente enviar a foto novamente.',
    serviceUnavailable: 'O serviço TitsBerry está temporariamente indisponível (erro do servidor). Por favor, tente novamente em alguns momentos.',
    processingFailed: 'Processamento falhou. Por favor, tente novamente.',
    failedToStart: 'Falha ao iniciar o processamento. Por favor, verifique sua foto e tente novamente.',
    tryAgainLater: 'Por favor, tente novamente mais tarde.',
    languageSet: 'Idioma definido para',
    termsAccepted: 'Termos aceitos',
    pleaseCompleteSetup: 'Por favor, complete a configuração primeiro',
    iAgree: 'Eu Concordo',
    uploadPhotoPrompt: '📷 Envie uma foto para processamento.\n⚠️ Não salvamos suas fotos — a imagem é usada apenas para processamento e depois excluída automaticamente.',
    optionNakedBreasts: 'Seios nus',
    optionFullNaked: 'Completamente nu',
    optionHappyNewYear: 'Feliz Ano Novo',
    optionBikini: 'Biquíni',
    optionUnderwear: 'Roupa íntima',
    processingTypeMediumSize: 'Tamanho médio',
    processingTypeBigSize: 'Tamanho grande',
    errorOccurred: '❌ Ocorreu um erro. Por favor, tente novamente mais tarde.',
    noPhotoFound: '❌ Nenhuma foto encontrada na mensagem.',
    invalidProcessingOption: 'Opção de processamento inválida',
    processingOptionNotFound: 'Opção de processamento não encontrada',
    photoExpiredOrNotFound: 'Foto expirada ou não encontrada. Por favor, envie novamente.',
    invalidPackage: 'Pacote inválido',
    packageNotFound: 'Pacote não encontrado',
    paymentInvalidData: 'Dados de pagamento inválidos. Por favor, tente novamente.',
    paymentPackageNotFound: 'Pacote de pagamento não encontrado. Por favor, tente novamente.',
    paymentAmountMismatch: 'Valor do pagamento não confere. Por favor, tente novamente.',
    paymentInvalidCurrency: 'Moeda de pagamento inválida. Por favor, use Telegram Stars.',
    paymentProcessingError: 'Ocorreu um erro ao processar seu pagamento. Por favor, tente novamente.',
    walletBerriesMessage: 'Bagas suculentas restantes: 🍒 {count}. Aproveite.',
    statsTitle: '📊 Estatísticas:',
    statsTotalStars: '⭐ Stars recebidas:',
    statsTotalUsers: '👥 Total de usuários:',
    statsTotalPayments: '🧾 Pagamentos:',
    statsAvgCheck: '📈 Ticket médio:',
    queueWaiting: '⏳ Sua solicitação está na fila. Por favor, aguarde...',
    rateLimitError: '⚠️ Muitas solicitações. Por favor, aguarde um momento e tente novamente.',
    stars: 'Estrelas',
    total: 'Total de bagas:',
    invoiceTitle: 'Bagas',
    invoiceDescription: 'bagas para processamento de foto',
    generation: 'baga',
    berryNominative: 'baga',
    berriesFew: 'bagas',
    generations: 'bagas',
    commandUploadDescription: 'Enviar uma foto para processamento',
    commandBuyDescription: 'Comprar bagas',
    commandWalletDescription: 'Verificar seu saldo de bagas',
    commandInviteDescription: 'Obtenha bagas grátis',
    commandLanguageDescription: 'Alterar o idioma',
    commandTermsDescription: 'Ver termos de serviço',
    commandPrivacyDescription: 'Ver política de privacidade',
    paymentAgreement: 'Ao prosseguir, você concorda com os [Termos de Uso](https://titsberry.github.io/terms.html) e a [Política de Privacidade](https://titsberry.github.io/privacy.html).',
    proceedButton: 'Prosseguir ➡️',
    freeBerries: '🍓 Bagas grátis',
    referralTitle: '💌 Compartilhe seu link com amigos.\n🎁 Para cada novo amigo que seguir seu link e gerar uma foto, você receberá 🍓 1 baga.',
    referralDescription: '🎁 Pegue o link — você pode fazer sua primeira geração gratuitamente.',
    shareButton: '📤 Compartilhar',
    referralRewardNotification: '🎉 Ótimas notícias! Seu amigo ativou o link de indicação e gerou sua primeira foto 😎.\n🍓 1 baga foi creditada na sua carteira.',
    buyBerries: '💳 Comprar bagas',
    selectPaymentMethod: 'Selecione o método de pagamento:',
    paymentMethodTelegramStars: '⭐ Telegram Stars',
    paymentMethodCrypto: '💎 Cripto',
    cryptoPaymentInstruction: 'Abra o link de pagamento, complete o pagamento e clique em "Verificar pagamento".',
    cryptoPaymentDetails: '🧾 Detalhes do Pagamento:',
    cryptoPaymentTransactionId: '🆔 ID da Transação:',
    cryptoPaymentAmount: '💰 Valor:',
    cryptoPaymentBerries: '🍓 Será creditado:',
    cryptoPaymentWalletAddress: '🏦 Endereço da Carteira:',
    cryptoPaymentImportant: 'ℹ️ Importante:',
    cryptoPaymentImportant1: '🔹 Transfira exatamente o valor especificado;',
    cryptoPaymentImportant2: '🔹 Após o pagamento, clique em "Verificar pagamento";',
    cryptoPaymentImportant3: '🔹 Aguarde o crédito de 🍓 em seu saldo.',
    payButton: '💳 Pagar',
    checkPaymentButton: '✅ Verificar pagamento',
    cancelButton: '❌ Cancelar',
    paymentNotConfirmed: 'O pagamento ainda não foi confirmado. Tente novamente em um minuto.',
    paymentChecking: 'Verificando status do pagamento...',
    paymentSuccess: 'Pagamento confirmado! As bagas foram adicionadas à sua carteira.',
    paymentFailed: 'Pagamento falhou ou expirou. Tente novamente.',
    paymentPartiallyPaid: 'Pagamento parcialmente pago. Por favor, complete o pagamento total.',
    paymentRateLimited: 'Por favor, aguarde antes de verificar novamente.',
    cryptoPaymentUnavailable: '⚠️ TON está temporariamente indisponível no NOWPayments. Tente novamente mais tarde ou use Telegram Stars para pagamento.',
    cryptoPaymentConversionError: '⚠️ Erro de conversão de moeda no NOWPayments. Tente novamente mais tarde ou use Telegram Stars para pagamento.',
    cryptoPaymentMinimalAmountError: '⚠️ O valor do pagamento é muito pequeno. O valor mínimo para TON é maior. Por favor, escolha um pacote com mais bagas ou use Telegram Stars para pagamento.',
  },
  ru: {
    languageSelection: 'Выбор языка:',
    termsText: `Нажимая кнопку "Я согласен" пользователь подтверждает, что ознакомился с [Политикой конфиденциальности](https://titsberry.github.io/privacy.html) и [Условиями использования](https://titsberry.github.io/terms.html), понимает их и принимает в полном объёме.`,
    welcome: '👋 Добро пожаловать! Используйте меню ниже для загрузки фотографий для обработки.',
    mainMenu: '📋 Главное меню:',
    uploadPhoto: '📷 Загрузить фото',
    buyGeneration: '💳 Купить ягоды',
    wallet: '📊 Мой баланс',
    changeLanguage: '🌐 Изменить язык',
    back: '⬅️ Назад',
    backToMenu: '⬅️ Вернуться в меню',
    photoReceived: 'Фото получено. Выберите размер груди.',
    selectProcessing: 'Выберите обработку.',
    processing: '⏳ Обработка… Подождите 2-3 минуты.',
    done: '✅ Готово.',
    remains: 'Осталось ягод:',
    noCredits: '💳 У вас не осталось ягод. Пожалуйста, приобретите пакет:',
    buyPackage: 'Пожалуйста, приобретите пакет ягод:',
    freeCredits: '🆓 Бесплатные ягоды:',
    paidCredits: '💳 Платные ягоды:',
    freeGenerations: '🆓 Бесплатные ягоды:',
    paidGenerations: '💳 Платные ягоды:',
    paymentSuccessful: '✅ Платеж успешен!',
    creditsAdded: 'добавлено на ваш счет.',
    errorProcessingPhoto: '❌ Ошибка обработки фото.',
    errorReceivingPhoto: '❌ Ошибка получения фото. Пожалуйста, попробуйте снова.',
    photoExpired: '⏰ Фото истекло. Пожалуйста, загрузите новое фото.',
    uploadNewPhoto: 'Пожалуйста, загрузите новое фото.',
    processingInProgress: 'Обработка уже выполняется. Пожалуйста, подождите.',
    pleaseWait: 'Пожалуйста, подождите.',
    minorDetected: '⚠️ Изображение не может быть обработано\n\nВ результате автоматической проверки безопасности изображение было идентифицировано как потенциально содержащее признаки несовершеннолетнего, поэтому обработка недоступна.\n\nПожалуйста, выберите другое изображение и попробуйте снова.',
    timeoutMessage: 'Обработка занимает больше времени, чем ожидалось. Задача может все еще выполняться. Пожалуйста, попробуйте позже или проверьте через несколько минут.',
    timeoutStillRunningMessage: '⏳ Высокая нагрузка на сервис: обработка займет больше времени.\n\nМы обрабатываем много запросов одновременно, поэтому ваша задача всё ещё выполняется. Фото будет отправлено сразу после завершения обработки. Спасибо за терпение!',
    fileUnavailable: 'Загруженный файл недоступен. Пожалуйста, попробуйте загрузить фото снова.',
    serviceUnavailable: 'Сервис TitsBerry временно недоступен (ошибка сервера). Пожалуйста, попробуйте снова через несколько моментов.',
    processingFailed: 'Обработка не удалась. Пожалуйста, попробуйте снова.',
    failedToStart: 'Не удалось начать обработку. Пожалуйста, проверьте ваше фото и попробуйте снова.',
    tryAgainLater: 'Пожалуйста, попробуйте позже.',
    languageSet: 'Язык установлен на',
    termsAccepted: 'Условия приняты',
    pleaseCompleteSetup: 'Пожалуйста, сначала завершите настройку',
    iAgree: 'Я согласен',
    uploadPhotoPrompt: '📷 Отправьте фото для обработки.\n⚠️ Мы не сохраняем ваши фотографии — изображение используется только для обработки и затем автоматически удаляется.',
    optionNakedBreasts: 'Обнаженная грудь',
    optionFullNaked: 'Полностью обнаженная',
    optionHappyNewYear: 'С Новым годом',
    optionBikini: 'Бикини',
    optionUnderwear: 'Нижнее белье',
    processingTypeMediumSize: 'Средний размер',
    processingTypeBigSize: 'Большой размер',
    errorOccurred: '❌ Произошла ошибка. Пожалуйста, попробуйте позже.',
    noPhotoFound: '❌ В сообщении не найдено фото.',
    invalidProcessingOption: 'Неверный вариант обработки',
    processingOptionNotFound: 'Вариант обработки не найден',
    photoExpiredOrNotFound: 'Фото истекло или не найдено. Пожалуйста, загрузите снова.',
    invalidPackage: 'Неверный пакет',
    packageNotFound: 'Пакет не найден',
    paymentInvalidData: 'Некорректные данные платежа. Пожалуйста, попробуйте снова.',
    paymentPackageNotFound: 'Пакет для оплаты не найден. Пожалуйста, попробуйте снова.',
    paymentAmountMismatch: 'Сумма платежа не совпадает. Пожалуйста, попробуйте снова.',
    paymentInvalidCurrency: 'Неверная валюта платежа. Пожалуйста, используйте Telegram Stars.',
    paymentProcessingError: 'Произошла ошибка при обработке платежа. Пожалуйста, попробуйте снова.',
    walletBerriesMessage: 'У тебя осталось сочных ягод: 🍓 {count}. Наслаждайтесь.',
    statsTitle: '📊 Статистика:',
    statsTotalStars: '⭐ Получено Stars:',
    statsTotalUsers: '👥 Всего пользователей:',
    statsTotalPayments: '🧾 Платежей:',
    statsAvgCheck: '📈 Средний чек:',
    queueWaiting: '⏳ Ваш запрос в очереди. Пожалуйста, подождите...',
    rateLimitError: '⚠️ Слишком много запросов. Пожалуйста, подождите немного и попробуйте снова.',
    stars: 'звёзд',
    total: 'Всего ягод:',
    invoiceTitle: 'Ягоды',
    invoiceDescription: 'ягод для обработки фото',
    generation: 'ягоду',
    berryNominative: 'ягода',
    berriesFew: 'ягоды',
    generations: 'ягод',
    commandUploadDescription: 'Загрузить фото для обработки',
    commandBuyDescription: 'Купить ягоды',
    commandWalletDescription: 'Проверить баланс ягод',
    commandInviteDescription: 'Получить бесплатные ягоды',
    commandLanguageDescription: 'Изменить язык',
    commandTermsDescription: 'Посмотреть условия использования',
    commandPrivacyDescription: 'Посмотреть политику конфиденциальности',
    paymentAgreement: 'Продолжая, вы соглашаетесь с [Условиями использования](https://titsberry.github.io/terms.html) и [Политикой конфиденциальности](https://titsberry.github.io/privacy.html).',
    proceedButton: 'Вперед ➡️',
    freeBerries: '🍓 Бесплатные ягоды',
    referralTitle: '💌 Делитесь ссылкой с друзьями.\n🎁 За каждого нового друга, который перейдёт по ссылке и сгенерирует фотографию, получите 🍓 1 ягоду.',
    referralDescription: '🎁 Лови ссылку — можно сделать первую генерацию бесплатно.',
    shareButton: '📤 Поделиться',
    referralRewardNotification: '🎉 Отличные новости! Ваш друг активировал реферальную ссылку и сгенерировал первую фотографию 😎.\n🍓 1 ягода зачислена на ваш кошелек.',
    buyBerries: '💳 Купить ягоды',
    selectPaymentMethod: 'Выберите способ оплаты:',
    paymentMethodTelegramStars: '⭐ Telegram Stars',
    paymentMethodCrypto: '💎 Криптовалюта',
    cryptoPaymentInstruction: 'Откройте ссылку на оплату, оплатите, затем нажмите "Проверить оплату".',
    cryptoPaymentDetails: '🧾 Детали платежа:',
    cryptoPaymentTransactionId: '🆔 ID сделки:',
    cryptoPaymentAmount: '💰 Сумма перевода:',
    cryptoPaymentBerries: '🍓 Начислится:',
    cryptoPaymentWalletAddress: '🏦 Адрес для перевода:',
    cryptoPaymentImportant: 'ℹ️ Важно:',
    cryptoPaymentImportant1: '🔹 Переведите ровно указанную сумму или чуть больше;',
    cryptoPaymentImportant2: '🔹 После оплаты нажмите «Проверить оплату»;',
    cryptoPaymentImportant3: '🔹 Ожидайте зачисление 🍓 на ваш кошелек.',
    payButton: '💳 Оплатить',
    checkPaymentButton: '✅ Проверить оплату',
    cancelButton: '❌ Отмена',
    paymentNotConfirmed: 'Платёж ещё не подтверждён. Попробуйте через минуту.',
    paymentChecking: 'Проверяю статус оплаты...',
    paymentSuccess: 'Оплата подтверждена! Ягоды добавлены на ваш кошелек.',
    paymentFailed: 'Оплата не прошла или истекла. Попробуйте снова.',
    paymentPartiallyPaid: 'Оплата частично выполнена. Пожалуйста, доплатите полную сумму.',
    paymentRateLimited: 'Пожалуйста, подождите перед повторной проверкой.',
    cryptoPaymentUnavailable: '⚠️ TON временно недоступен в NOWPayments. Попробуйте позже или используйте Telegram Stars для оплаты.',
    cryptoPaymentConversionError: '⚠️ Ошибка конвертации валют в NOWPayments. Попробуйте позже или используйте Telegram Stars для оплаты.',
    cryptoPaymentMinimalAmountError: '⚠️ Сумма платежа слишком мала. Минимальная сумма для TON выше. Пожалуйста, выберите пакет с большим количеством ягод или используйте Telegram Stars для оплаты.',
  },
};

export function getTranslation(lang: Language | null | undefined): Translations {
  return translations[lang || 'en'];
}

export function formatBerriesCount(lang: Language | null | undefined, count: number): string {
  const t = getTranslation(lang);
  const n = Math.abs(Math.trunc(count));

  // Russian plural rules (1 / 2-4 / 5+)
  if ((lang || 'en') === 'ru') {
    const mod10 = n % 10;
    const mod100 = n % 100;

    if (mod10 === 1 && mod100 !== 11) {
      return `${count} ${t.generation}`;
    }
    if (mod10 >= 2 && mod10 <= 4 && !(mod100 >= 12 && mod100 <= 14)) {
      return `${count} ${t.berriesFew}`;
    }
    return `${count} ${t.generations}`;
  }

  // Simple singular/plural for other languages
  if (n === 1) {
    return `${count} ${t.generation}`;
  }
  return `${count} ${t.generations}`;
}

export function formatBerriesCountNominative(lang: Language | null | undefined, count: number): string {
  const t = getTranslation(lang);
  const n = Math.abs(Math.trunc(count));

  // Russian plural rules (1 / 2-4 / 5+)
  if ((lang || 'en') === 'ru') {
    const mod10 = n % 10;
    const mod100 = n % 100;

    if (mod10 === 1 && mod100 !== 11) {
      return `${count} ${t.berryNominative}`;
    }
    if (mod10 >= 2 && mod10 <= 4 && !(mod100 >= 12 && mod100 <= 14)) {
      return `${count} ${t.berriesFew}`;
    }
    return `${count} ${t.generations}`;
  }

  // Simple singular/plural for other languages
  if (n === 1) {
    return `${count} ${t.berryNominative}`;
  }
  return `${count} ${t.generations}`;
}

export function getLanguageName(lang: Language): string {
  const names: Record<Language, string> = {
    en: 'English',
    hi: 'हिन्दी (Hindi)',
    id: 'Bahasa Indonesia',
    pt: 'Português (Brasil)',
    ru: 'Русский',
  };
  return names[lang];
}

