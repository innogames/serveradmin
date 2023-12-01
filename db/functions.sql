CREATE OR REPLACE FUNCTION get_last_two_parts(domain VARCHAR)
RETURNS VARCHAR AS $$
DECLARE
  parts TEXT[];
BEGIN
  parts := STRING_TO_ARRAY(domain, '.');
  -- Return the concatenated last two parts if the array has at least two elements
  IF array_length(parts, 1) >= 2 THEN
    RETURN parts[array_length(parts, 1) - 1] || '.' || parts[array_length(parts, 1)];
  ELSE
    -- Return the domain itself if it has less than two parts
    RETURN domain;
  END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;