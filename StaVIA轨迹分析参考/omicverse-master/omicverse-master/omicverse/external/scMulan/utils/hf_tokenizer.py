from transformers import PreTrainedTokenizer


class scMulanTokenizer(PreTrainedTokenizer):
    def encode(self, text, *args, **kwargs):
        # scMulan calls ``tokenizer.encode(list_of_token_strings)``
        # treating the list as a pre-tokenized sequence — i.e. one id
        # per element. transformers <= 4.40 silently flattened that
        # input; >= 4.45 treats list-of-str as a *batch* and returns
        # ``[[id], [id], ...]``. Detect the pre-tokenized form here and
        # return the flat id list directly, matching the published
        # checkpoint's expected input shape (no retraining needed).
        if isinstance(text, list) and text and all(isinstance(t, str) for t in text):
            return [self.stoi[t] for t in text]
        return super().encode(text, *args, **kwargs)

    def __init__(self, chars):
        self.chars = chars
        self.stoi = { ch:i for i,ch in enumerate(self.chars) }
        self.itos = { i:ch for i,ch in enumerate(self.chars) }
        super().__init__()

    def _tokenize(self, text):
        # PreTrainedTokenizer.tokenize() expects this to return a list of
        # *string* tokens; the id lookup is handled by the downstream
        # `convert_tokens_to_ids` -> `_convert_token_to_id` chain. Earlier
        # transformers versions tolerated returning ids directly here,
        # but >= 4.45 strictly enforces the string-token contract.
        return text.split('##')

    def _convert_token_to_id(self, token):
        # Accept either a string (the documented HF contract) or an int
        # (legacy scMulan callers that pre-encoded the prompt) — falling
        # back to identity for ints keeps the model.generate flow working
        # when callers pass already-encoded ids straight through.
        if isinstance(token, int):
            return token
        return self.stoi[token]

    def _convert_id_to_token(self, index):
        return self.itos[index]

    def convert_tokens_to_string(self, tokens):
        return '##'.join(tokens)
    
    def get_vocab(self):
        import transformers
        if transformers.__version__ <= "4.40":
            return self.stoi
        else:
            try:
                return self.get_stoi()
            except AttributeError:
                return self.stoi
    
    @property
    def vocab_size(self) -> int:
        return len(self.stoi)
