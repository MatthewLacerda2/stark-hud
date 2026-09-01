import type { Item, Notification } from "@/lib/schemas/board";
import { Box } from "@/components/board/items/box";
import { Chart } from "@/components/board/items/chart";
import { Clock } from "@/components/board/items/clock";
import { Feed } from "@/components/board/items/feed";
import { Image } from "@/components/board/items/image";
import { Video } from "@/components/board/items/video";
import { Inbox } from "@/components/board/items/inbox";
import { List } from "@/components/board/items/list";
import { Note } from "@/components/board/items/note";
import { Text } from "@/components/board/items/text";

/** Render one item by kind. The union is exhaustive, so a new kind will not compile. */
export function ItemView({
  item,
  notifications,
}: {
  item: Item;
  notifications: Notification[];
}) {
  const payload = item.payload;
  switch (payload.kind) {
    case "note":
      return <Note payload={payload} />;
    case "text":
      return <Text payload={payload} />;
    case "list":
      return <List id={item.id} payload={payload} />;
    case "box":
      return <Box payload={payload} />;
    case "image":
      return <Image id={item.id} payload={payload} />;
    case "video":
      return <Video id={item.id} payload={payload} />;
    case "chart":
      return <Chart payload={payload} />;
    case "inbox":
      return <Inbox payload={payload} notifications={notifications} />;
    case "feed":
      return <Feed id={item.id} payload={payload} />;
    case "clock":
      // Its height decides whether the date fits; the payload says nothing.
      return <Clock rows={item.h} />;
  }
}
