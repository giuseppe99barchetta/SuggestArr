# Rating prompts (Telegram and Discord)

SuggestArr can message you on **Telegram** or **Discord** a while after you finish a title and ask how you liked it, with buttons **1 to 10**. One tap saves the rating, the same rating you can edit in **Profile → Recommendation history**, so recommendations learn from it.

## Set up

1. Create a Telegram bot with @BotFather and **use it only for SuggestArr** (see limits below).
2. Open a private chat with the bot and send it a message. Find your numeric chat id (for example with @userinfobot).
3. In **Profile → Notifications**, choose Telegram and save the bot's `sendMessage` URL with your own chat id:
   `https://api.telegram.org/bot<token>/sendMessage?chat_id=<your numeric id>`
   (Prompts need a private chat: group chats and negative ids are not accepted.)
4. Link your media server account, then switch on **Rate what you watch** and choose how many hours to wait (0 to 48, default 12). A delay keeps you from being asked mid-binge.

## Set up Discord

Discord needs a bot of your own and a SuggestArr address that Discord can reach over HTTPS (for example behind your reverse proxy).

1. In the [Discord Developer Portal](https://discord.com/developers/applications) create an application and add a **Bot**. Copy the **bot token** (Bot page) and the **public key** (General Information page).
2. Make sure the bot can message you directly: share a server with it, or install the app to your own account, and allow direct messages from server members.
3. In Discord turn on **Developer Mode** (User Settings, Advanced), right-click yourself and **Copy User ID**.
4. In SuggestArr open **Profile, Rate what you watch**, choose **Discord**, enter the token, public key and your user ID and press **Save**. Prompts can stay off for now.
5. Copy the **Interactions Endpoint URL** shown there (it already includes your sub-path, if any) and paste it into General Information, Interactions Endpoint URL, in the Developer Portal. Discord checks it immediately; this only works after step 4.
6. Press **Send test message**. If Discord refuses, the message says why (typically the bot cannot DM you).
7. Switch **Ask me to rate what I watched** on.

A tap edits the message to "Saved: 8/10 for ..." and removes the buttons. The bot token is stored with your account and is never shown again.

## What is asked

- A movie is asked once. A show is asked once, not per episode; the wait counts from the last episode you played.
- Titles you already rated, or excluded, are never asked.
- Only plays after you switched the setting on are asked about; older history is not. At most 5 prompts are sent every 15 minutes.
- Only you can answer: a tap counts only from your own private chat (Telegram) or your own DM with your own bot (Discord), while prompts are on.
- Changing where prompts go (the channel, the Discord key or user, or the Telegram bot or chat, or removing the Telegram destination) permanently disables the buttons of messages already sent; those titles are not asked again.

## Limits

- ntfy is not supported (it allows at most 3 buttons, and its buttons cannot prove who tapped). A plain Discord webhook URL cannot carry buttons either; Discord needs the bot described above.
- Telegram taps are read with `getUpdates`, so no public address is needed for Telegram; Discord delivers taps to SuggestArr instead, so Discord needs a reachable HTTPS address. This is why the bot must be dedicated: a bot that has a webhook set cannot be polled (HTTP 409), and any other program reading the same bot would lose the updates SuggestArr consumes.
- A Telegram tap is picked up within about 20 seconds; a Discord tap is immediate.
- Delivery is at most once: if SuggestArr cannot tell whether a message was sent (for example a timeout), it does not send it again.
- Prompts use the media server history SuggestArr last read. A replay that starts in the seconds between that read and the message is not noticed.
- History is read newest first with a page limit. If a very large history is cut short, SuggestArr waits for the next run instead of prompting.
