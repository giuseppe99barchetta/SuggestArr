# Rating prompts (Telegram)

SuggestArr can message you a while after you finish a title and ask how you liked it, with buttons **1 to 10**. One tap saves the rating, the same rating you can edit in **Profile → Recommendation history**, so recommendations learn from it.

## Set up

1. Create a Telegram bot with @BotFather and **use it only for SuggestArr** (see limits below).
2. Open a private chat with the bot and send it a message. Find your numeric chat id (for example with @userinfobot).
3. In **Profile → Notifications**, choose Telegram and save the bot's `sendMessage` URL with your own chat id:
   `https://api.telegram.org/bot<token>/sendMessage?chat_id=<your numeric id>`
   (Prompts need a private chat: group chats and negative ids are not accepted.)
4. Link your media server account, then switch on **Rate what you watch** and choose how many hours to wait (0 to 48, default 12). A delay keeps you from being asked mid-binge.

## What is asked

- A movie is asked once. A show is asked once, not per episode; the wait counts from the last episode you played.
- Titles you already rated, or excluded, are never asked.
- Only plays after you switched the setting on are asked about; older history is not. At most 5 prompts are sent every 15 minutes.
- Only you can answer: a tap counts only from your own private chat, through your own bot.

## Limits

- Discord and ntfy are not supported yet (a webhook URL cannot receive a button tap; ntfy allows at most 3 buttons).
- SuggestArr reads taps with Telegram `getUpdates`, so no public address is needed. This is why the bot must be dedicated: a bot that has a webhook set cannot be polled (HTTP 409), and any other program reading the same bot would lose the updates SuggestArr consumes.
- A tap is picked up within about 20 seconds.
- Delivery is at most once: if SuggestArr cannot tell whether a message was sent (for example a timeout), it does not send it again.
- Prompts use the media server history SuggestArr last read. A replay that starts in the seconds between that read and the message is not noticed.
- History is read newest first with a page limit. If a very large history is cut short, SuggestArr waits for the next run instead of prompting.
