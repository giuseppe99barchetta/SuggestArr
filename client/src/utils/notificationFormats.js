/** Chat services SuggestArr can post to, shared by shared webhooks and personal notifications. */
export const CHAT_FORMATS = [
  { value: 'discord', label: 'Discord', icon: 'fab fa-discord', urlLabel: 'Discord webhook URL', placeholder: 'https://discord.com/api/webhooks/…', hint: 'Channel settings → Integrations → Webhooks → Copy URL.' },
  { value: 'telegram', label: 'Telegram', icon: 'fab fa-telegram-plane', urlLabel: 'Bot sendMessage URL', placeholder: 'https://api.telegram.org/bot<token>/sendMessage?chat_id=123', hint: 'Your bot token from @BotFather, plus the chat_id to post in.' },
  { value: 'ntfy', label: 'ntfy', icon: 'fas fa-bell', urlLabel: 'Topic URL', placeholder: 'https://ntfy.sh/my-suggestarr', hint: 'The server and topic your phone subscribes to.' },
];

/** The signed SuggestArr payload, for automations rather than people. */
export const JSON_FORMAT = { value: 'json', label: 'Webhook', icon: 'fas fa-code', urlLabel: 'Destination URL', placeholder: 'https://hooks.example.com/suggestarr', hint: 'Receives a signed JSON POST; it must answer 2xx quickly.' };
