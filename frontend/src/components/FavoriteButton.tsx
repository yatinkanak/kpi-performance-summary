import { useAddFavorite, useFavorites, useRemoveFavorite } from "../api/client";

// Star toggle that bookmarks a (company, KPI) pair. `kpi` is the KPI name.
export default function FavoriteButton({
  ticker,
  kpi,
}: {
  ticker: string;
  kpi: string;
}) {
  const { data: favorites } = useFavorites();
  const add = useAddFavorite();
  const remove = useRemoveFavorite();

  const isFav = favorites?.some((f) => f.ticker === ticker && f.kpi === kpi) ?? false;
  const pending = add.isPending || remove.isPending;

  const toggle = (e: React.MouseEvent) => {
    e.preventDefault(); // don't trigger an enclosing link
    e.stopPropagation();
    if (isFav) remove.mutate({ ticker, kpi });
    else add.mutate({ ticker, kpi });
  };

  return (
    <button
      type="button"
      className={`star${isFav ? " on" : ""}`}
      onClick={toggle}
      disabled={pending}
      aria-pressed={isFav}
      title={isFav ? "Remove from favorites" : "Add to favorites"}
    >
      {isFav ? "★" : "☆"}
    </button>
  );
}
