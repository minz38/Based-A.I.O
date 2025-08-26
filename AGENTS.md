# AGENTS

## Guidelines
- Use 4 spaces for indentation.
- Prefer double quotes for strings.
- Place new Discord features as cogs inside `extensions/` and register them in `configs/bot_config.json` to activate.
- Run `python -m py_compile` on changed Python files before committing.
- Update this file with any new project knowledge.

## Notes
- `image_upvote` extension allows images in channel `1003337674008055919` to be uploaded once they receive five `:arrow_upvote:` reactions. Admins can force the upload via a message context menu.
- Uploaded images are saved to `cdn/ImageUploads/` using the naming pattern `<user_id>-<message_id>_<nn><extension>` where `nn` increments for multiple attachments. The feature reads environment variables `IMAGE_UPVOTE_CHANNEL_ID`, `IMAGE_UPVOTE_EMOJI_NAME`, and `IMAGE_UPVOTE_THRESHOLD` (defaults match previous hardcoded values).
- After a successful upload the bot reacts with `:white_check_mark:` to mark processed messages and counts emoji reactions each time to ensure accuracy after restarts.
