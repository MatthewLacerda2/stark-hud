import type { Item } from "@/lib/schemas/board";
import { Box } from "@/components/board/items/box";
import { Chart } from "@/components/board/items/chart";
import { Image } from "@/components/board/items/image";
import { Video } from "@/components/board/items/video";
import { List } from "@/components/board/items/list";
import { Note } from "@/components/board/items/note";
import { Notification } from "@/components/board/items/notification";
import { Text } from "@/components/board/items/text";

/** Render one item by kind. The union is exhaustive, so a new kind will not compile. */
export function ItemView({ item }: { item: Item }) {
  const payload = item.payload;
  switch (payload.kind) {
    case "note":
      return <Note payload={payload} />;
    case "text":
      return <Text payload={payload} />;
    case "list":
      return <List payload={payload} />;
    case "box":
      return <Box payload={payload} />;
    case "image":
      return <Image id={item.id} payload={payload} />;
    case "video":
      return <Video id={item.id} payload={payload} />;
    case "chart":
      return <Chart payload={payload} />;
    case "notification":
      return <Notification payload={payload} />;
  }
}
