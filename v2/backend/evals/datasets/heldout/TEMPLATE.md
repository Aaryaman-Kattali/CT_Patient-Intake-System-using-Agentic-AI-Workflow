# Held-out conversation template

Write one conversation per file, for example `heldout-01.md`, in this folder.
Use made-up people only: emails ending in `@example.com`, and phone numbers from
`202-555-0100` to `202-555-0199`.

## Form

One of: `family inquiry for myself`, `family inquiry for someone else`, `provider referral`

## Conversation

One line per turn the person takes, in order, each starting with `- `.

- Typed text: write exactly what the person types.
- A button: start with `[button]` and write the words on the button.
- A button that opens a text box: `[button] <button words>: <what they type in the box>`

The form's own messages are not written here. After the last line, the form is sent if it
is on the review screen.

- [button] <words on a button>
- <what the person types>
- <what the person types>

## Expected

One line per field you want checked, as `field: value`. Leave out fields you don't want
checked.

- Dates: `YYYY-MM-DD`. Phone numbers: `202-555-01XX`. Buttons: the words on the button.
- Instead of a value you can write a status: `skipped`, `answer later` or `not known`.

Field names: `kind of form`, `who this form is for`, `your name`, `full name`,
`date of birth`, `how to contact you`, `phone number`, `email address`, `home address`,
`help asked for`, `referring provider`, `referral type`, `referral date`, `how it was sent`,
`name to use`, `gender`

- <field>: <value>
