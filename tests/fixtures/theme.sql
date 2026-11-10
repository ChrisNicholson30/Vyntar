-- Named parameters and identifiers stay neutral.
SELECT theme_name, COUNT(*) AS selections
FROM theme_preferences
WHERE enabled = TRUE AND contrast >= 4.5
GROUP BY theme_name
ORDER BY selections DESC;
